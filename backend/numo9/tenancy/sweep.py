"""Tenant-isolation router sweep (A-01-T09), run by ``manage.py tenant_sweep``.

Every URL pattern of the URLconf is enumerated and classified:

- **organisation-scoped** — the URL carries an organisation (``/o/<org>/…`` or
  ``/api/v<n>/o/<org>/…``; the segment must be a named group called ``org``);
- **exempt** — not organisation-scoped and listed in ``EXEMPT_ROUTES`` /
  ``settings.TENANT_SWEEP_EXEMPT`` (health check, Django admin, …);
- anything else fails the sweep: an endpoint without an organisation that is not on the exempt
  list, or a pattern whose URL cannot be built.

For every organisation-scoped endpoint the sweep creates a row of the view's model in Org 1 and in
Org 2 (when the view names a model), signs in as the owner of Org 2, and sends GET, POST, PUT,
PATCH and DELETE:

1. to the Org 1 URL with Org 1's object → must be ``404``;
2. to the Org 2 URL with Org 1's object (only when the URL has an object id) → must be ``404``;
   (``405`` for a verb the view does not support is accepted in 1–2: it reveals nothing);
3. to the Org 2 URL with Org 2's object → must **not** be ``404`` for at least one verb — otherwise
   the URL was built wrongly and steps 1–2 proved nothing.

Any other answer is a leak. Everything runs in one transaction that is rolled back.
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from typing import Any

from django.apps import apps
from django.conf import settings
from django.db import models, transaction
from django.test import Client
from django.test.utils import override_settings
from django.urls import URLPattern, URLResolver, get_resolver

from .middleware import ORG_PATH_RE
from .models import Organisation, OrganisationMember, OrganisationRole, OrgOwnedModel

VERBS: tuple[str, ...] = ("get", "post", "put", "patch", "delete")
# 404 is the expected answer; 405 (verb not supported by the view) reveals nothing about the
# organisation or the object either, so it is accepted.
SAFE_STATUSES: frozenset[int] = frozenset({404, 405})
ORG_PARAM = "org"
EXEMPT_ROUTES: tuple[str, ...] = (r"^healthz$", r"^admin/")

# Model label -> callable(organisation) returning a saved row. Register models whose required
# fields the generic factory cannot fill (see ``make_row``).
SWEEP_FACTORIES: dict[str, Callable[[Organisation], OrgOwnedModel]] = {}


@dataclass
class Endpoint:
    route: str  # regex of the full pattern without anchors
    callback: Callable[..., Any]
    groups: dict[str, str] = field(default_factory=dict)  # named group -> its sub-regex
    display: str = ""  # the pattern as written in urls.py (shown in the report)

    def __post_init__(self) -> None:
        self.display = self.display or self.route

    @property
    def view_class(self) -> type | None:
        return getattr(self.callback, "cls", None) or getattr(self.callback, "view_class", None)


@dataclass
class Result:
    route: str  # as written in urls.py
    kind: str  # "scoped" | "exempt" | "error"
    statuses: dict[str, str] = field(default_factory=dict)
    problems: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.problems


# ---- URL enumeration and building --------------------------------------------------------------


def _strip_anchors(regex: str) -> str:
    regex = regex.removeprefix("^")
    for end in ("\\Z", "$"):
        regex = regex.removesuffix(end)
    return regex


def iter_endpoints(urlconf: str | None = None) -> Iterator[Endpoint]:
    def walk(patterns: list[Any], prefix: str, shown: str) -> Iterator[Endpoint]:
        for entry in patterns:
            regex = prefix + _strip_anchors(entry.pattern.regex.pattern)
            display = shown + _strip_anchors(str(entry.pattern))
            if isinstance(entry, URLResolver):
                yield from walk(entry.url_patterns, regex, display)
            elif isinstance(entry, URLPattern):
                yield Endpoint(
                    route=regex,
                    callback=entry.callback,
                    groups=_named_groups(regex),
                    display=display,
                )

    yield from walk(get_resolver(urlconf).url_patterns, "", "")


def _group_spans(regex: str) -> Iterator[tuple[int, int, str, str]]:
    """(start, end, name, sub-regex) of every top-level named group ``(?P<name>…)``."""
    i = 0
    while (start := regex.find("(?P<", i)) != -1:
        name_end = regex.index(">", start)
        name = regex[start + 4 : name_end]
        depth, j = 1, name_end + 1
        while depth:
            char = regex[j]
            if char == "\\":
                j += 2
                continue
            depth += {"(": 1, ")": -1}.get(char, 0)
            j += 1
        yield start, j, name, regex[name_end + 1 : j - 1]
        i = j


def _named_groups(regex: str) -> dict[str, str]:
    return {name: sub for _, _, name, sub in _group_spans(regex)}


def build_path(endpoint: Endpoint, values: dict[str, str]) -> str | None:
    """Concrete path for the endpoint, or ``None`` when the pattern cannot be filled."""
    out, last = [], 0
    for start, end, name, _sub in _group_spans(endpoint.route):
        if name not in values:
            return None
        out.extend([endpoint.route[last:start], values[name]])
        last = end
    out.append(endpoint.route[last:])
    path = "/" + re.sub(r"\\(.)", r"\1", "".join(out))
    return path if re.fullmatch(endpoint.route, path[1:]) else None


# ---- sweep data -------------------------------------------------------------------------------


def view_model(endpoint: Endpoint) -> type[OrgOwnedModel] | None:
    cls = endpoint.view_class
    queryset = getattr(cls, "queryset", None)
    model = getattr(queryset, "model", None)
    if model is None:
        meta = getattr(getattr(cls, "serializer_class", None), "Meta", None)
        model = getattr(meta, "model", None)
    if isinstance(model, type) and issubclass(model, OrgOwnedModel):
        return model
    return None


def make_row(model: type[OrgOwnedModel], organisation: Organisation) -> OrgOwnedModel:
    """A saved row of ``model`` in ``organisation`` (registered factory or generic fill)."""
    factory = SWEEP_FACTORIES.get(model._meta.label)
    if factory is not None:
        return factory(organisation)
    values: dict[str, Any] = {}
    for f in model._meta.concrete_fields:
        if f.primary_key or f.has_default() or f.null or f.name in ("organisation",):
            continue
        if isinstance(f, models.ForeignKey):
            target = f.related_model
            if isinstance(target, type) and issubclass(target, OrgOwnedModel):
                values[f.name] = make_row(target, organisation)
                continue
            raise ValueError(f"register a SWEEP_FACTORIES entry for {model._meta.label}")
        if f.choices:
            values[f.name] = f.choices[0][0]
        elif isinstance(f, models.CharField | models.TextField):
            values[f.name] = "sweep"
        elif isinstance(f, models.IntegerField | models.DecimalField | models.FloatField):
            values[f.name] = 0
        elif isinstance(f, models.BooleanField):
            values[f.name] = False
        elif not getattr(f, "auto_now_add", False) and not getattr(f, "auto_now", False):
            raise ValueError(f"register a SWEEP_FACTORIES entry for {model._meta.label}")
    return model._base_manager.create(organisation=organisation, **values)


def _object_value(name: str, obj: OrgOwnedModel | None, sub_regex: str) -> str:
    if obj is not None:
        if name in ("pk", "id"):
            return str(obj.pk)
        if hasattr(obj, name):
            return str(getattr(obj, name))
    for candidate in (str(uuid.uuid4()), "1", "sweep"):
        if re.fullmatch(sub_regex, candidate):
            return candidate
    return "sweep"


def _values(endpoint: Endpoint, org: Organisation, obj: OrgOwnedModel | None) -> dict[str, str]:
    values = {ORG_PARAM: str(org.public_id)}
    for name, sub in endpoint.groups.items():
        if name != ORG_PARAM:
            values[name] = _object_value(name, obj, sub)
    return values


def _is_exempt(route: str, extra: tuple[str, ...]) -> bool:
    return any(re.search(p, route) for p in (*EXEMPT_ROUTES, *extra))


def _request_all(client: Client, path: str) -> dict[str, int]:
    return {verb: getattr(client, verb)(path).status_code for verb in VERBS}


def _sweep_endpoint(
    endpoint: Endpoint, client: Client, org1: Organisation, org2: Organisation
) -> Result:
    result = Result(route=endpoint.display, kind="scoped")
    model = view_model(endpoint)
    try:
        row1 = make_row(model, org1) if model else None
        row2 = make_row(model, org2) if model else None
    except ValueError as exc:
        result.problems.append(str(exc))
        return result
    foreign = build_path(endpoint, _values(endpoint, org1, row1))
    own = build_path(endpoint, _values(endpoint, org2, row2))
    if foreign is None or own is None:
        result.kind, result.problems = "error", ["URL could not be built from the pattern"]
        return result
    checks: list[tuple[str, str]] = [("org1", foreign)]
    has_object = any(name != ORG_PARAM for name in endpoint.groups)
    if has_object and row1 is not None:
        cross_values = {**_values(endpoint, org1, row1), ORG_PARAM: str(org2.public_id)}
        cross = build_path(endpoint, cross_values)
        if cross is not None:
            checks.append(("org2+org1-id", cross))
    for label, path in checks:
        for verb, status in _request_all(client, path).items():
            result.statuses[f"{label}:{verb.upper()}"] = str(status)
            if status not in SAFE_STATUSES:
                result.problems.append(f"{verb.upper()} {path} as Org 2 → {status}, expected 404")
    own_statuses = _request_all(client, own)
    result.statuses.update({f"own:{v.upper()}": str(s) for v, s in own_statuses.items()})
    if all(status == 404 for status in own_statuses.values()):
        result.problems.append(
            f"{own} answers 404 to every verb even for its own organisation — the sweep cannot "
            "reach this endpoint (check the URL pattern and the ``org`` group name)"
        )
    return result


class _Rollback(Exception):
    pass


def run_sweep(urlconf: str | None = None, exempt: tuple[str, ...] = ()) -> list[Result]:
    """Sweep every endpoint of ``urlconf``; all data created is rolled back."""
    extra = (*tuple(getattr(settings, "TENANT_SWEEP_EXEMPT", ())), *exempt)
    results: list[Result] = []
    user_model = apps.get_model(settings.AUTH_USER_MODEL)
    with override_settings(ROOT_URLCONF=urlconf or settings.ROOT_URLCONF, ALLOWED_HOSTS=["*"]):
        try:
            with transaction.atomic():
                org1 = Organisation.objects.create(name="Sweep Org 1")
                org2 = Organisation.objects.create(name="Sweep Org 2")
                user = user_model.objects.create_user(
                    f"sweep-{uuid.uuid4().hex}@example.invalid", name="Sweep"
                )
                OrganisationMember.objects.create(
                    organisation=org2, user=user, role=OrganisationRole.OWNER
                )
                client = Client(raise_request_exception=False)
                client.force_login(user)
                for endpoint in iter_endpoints(urlconf):
                    probe = build_path(endpoint, _values(endpoint, org1, None))
                    scoped = probe is not None and ORG_PATH_RE.match(probe) is not None
                    if scoped:
                        results.append(_sweep_endpoint(endpoint, client, org1, org2))
                    elif _is_exempt(endpoint.display, extra):
                        results.append(Result(route=endpoint.display, kind="exempt"))
                    else:
                        why = (
                            "URL could not be built from the pattern"
                            if probe is None
                            else "not organisation-scoped and not on the exempt list"
                        )
                        results.append(Result(route=endpoint.display, kind="error", problems=[why]))
                raise _Rollback
        except _Rollback:
            pass
    return results
