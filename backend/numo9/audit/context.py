"""Who is acting, from where: the audit context of a request or a job (A-04-T04).

``record()`` asks ``current_actor()`` for the actor, IP address, device and request id of every
event it writes, so callers never pass them. In order of precedence:

1. an explicit ``audit_context(...)`` block (tests, scripts, impersonation flows);
2. **a background job** (A-08: ``current_job()``) — attributed to ``System: <job name>``
   (gap-44) with the job's id and type and, when a person started it, who did, in ``meta``;
3. **a request** (``AuditContextMiddleware``) — the signed-in user (read when the event is
   written, so a sign-in during the request counts), or the impersonated user with the platform
   staff member as ``impersonator`` when ``request.audit_impersonator`` is set (U-06);
   the client's IP (``REMOTE_ADDR``, or the address the trusted proxies forwarded —
   ``NUMO9_TRUSTED_PROXY_COUNT``), the User-Agent, and the request id;
4. **a Celery task** that is not a job — ``System: <task name>``;
5. anything else (a management command, a shell) — ``System`` (with the command in ``meta``).

**Request id.** ``AuditContextMiddleware`` takes a well-formed ``X-Request-ID`` from the client or
proxy (8–64 characters of ``A–Z a–z 0–9 . _ -``) or makes one, returns it in the ``X-Request-ID``
response header and binds it to every log line of the request (structlog ``request_id``), so an
audit event, a log line and a support ticket can be matched.
"""

from __future__ import annotations

import ipaddress
import re
import sys
import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field, replace
from typing import Any

import structlog
from django.conf import settings
from django.http import HttpRequest, HttpResponse

from .models import ActorKind

REQUEST_ID_HEADER = "X-Request-ID"
_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{8,64}$")


@dataclass(frozen=True)
class Actor:
    """Who an event is attributed to, and where the change came from."""

    kind: str = ActorKind.SYSTEM.value
    user: Any = None
    impersonator: Any = None
    label: str = "System"
    ip: str | None = None
    user_agent: str = ""
    request_id: str = ""
    meta: dict[str, Any] = field(default_factory=dict)


_explicit: ContextVar[Actor | None] = ContextVar("numo9_audit_actor", default=None)
_request: ContextVar[HttpRequest | None] = ContextVar("numo9_audit_request", default=None)


@contextmanager
def audit_context(**fields: Any) -> Iterator[Actor]:
    """Attribute every event in the block to the given actor (fields of ``Actor``)."""
    actor = Actor(**fields)
    token = _explicit.set(actor)
    try:
        yield actor
    finally:
        _explicit.reset(token)


def current_request() -> HttpRequest | None:
    return _request.get()


# ---- request facts -----------------------------------------------------------------------------


def _valid_ip(value: str) -> str | None:
    try:
        return str(ipaddress.ip_address(value.strip()))
    except ValueError:
        return None


def client_ip(request: Any) -> str | None:
    """The client's address: ``REMOTE_ADDR``, or the one the trusted proxies forwarded.

    With ``NUMO9_TRUSTED_PROXY_COUNT = n`` (the proxies in front of the app, e.g. 1 for Caddy),
    the client is the n-th address from the right of ``X-Forwarded-For`` — addresses further left
    were written by the client and cannot be trusted.
    """
    meta = getattr(request, "META", None) or {}
    trusted = int(getattr(settings, "NUMO9_TRUSTED_PROXY_COUNT", 0) or 0)
    if trusted > 0:
        hops = [h for h in str(meta.get("HTTP_X_FORWARDED_FOR", "")).split(",") if h.strip()]
        if len(hops) >= trusted:
            forwarded = _valid_ip(hops[-trusted])
            if forwarded:
                return forwarded
    return _valid_ip(str(meta.get("REMOTE_ADDR", "")))


def user_agent_of(request: Any) -> str:
    meta = getattr(request, "META", None) or {}
    return str(meta.get("HTTP_USER_AGENT", ""))[:512]


def request_id_of(request: Any) -> str:
    value = getattr(request, "request_id", "")
    return str(value) if value else ""


def user_label(user: Any) -> str:
    name = getattr(user, "name", "") or ""
    email = getattr(user, "email", "") or ""
    return (f"{name} ({email})" if name and email else name or email)[:300]


def _authenticated(user: Any) -> Any:
    return user if user is not None and getattr(user, "is_authenticated", False) else None


def _from_request(request: HttpRequest) -> Actor:
    facts: dict[str, Any] = {
        "ip": client_ip(request),
        "user_agent": user_agent_of(request),
        "request_id": request_id_of(request),
    }
    user = _authenticated(getattr(request, "user", None))
    impersonator = _authenticated(getattr(request, "audit_impersonator", None))
    if user is not None and impersonator is not None:
        return Actor(
            kind=ActorKind.IMPERSONATION,
            user=user,
            impersonator=impersonator,
            label=f"{user_label(user)} — signed in by {user_label(impersonator)}"[:300],
            **facts,
        )
    if user is not None:
        return Actor(kind=ActorKind.USER, user=user, label=user_label(user), **facts)
    return Actor(kind=ActorKind.SYSTEM, label="Anonymous", **facts)


def _from_job() -> Actor | None:
    from numo9.jobs.runtime import current_job
    from numo9.jobs.serializers import job_label

    run = current_job()
    if run is None:
        return None
    job: dict[str, Any] = {"id": str(run.public_id), "task": run.task_name}
    starter = run.created_by if run.created_by_id else None
    if starter is not None:
        job["started_by"] = {"id": str(starter.public_id), "label": user_label(starter)}
    return Actor(
        kind=ActorKind.SYSTEM, label=f"System: {job_label(run.task_name)}", meta={"job": job}
    )


def _from_celery() -> Actor | None:
    try:
        from celery import current_task
    except ImportError:  # pragma: no cover — Celery is a runtime dependency
        return None
    task = current_task
    request = getattr(task, "request", None) if task else None
    if not task or getattr(request, "id", None) is None:
        return None
    name = str(getattr(task, "label", None) or task.name)
    return Actor(kind=ActorKind.SYSTEM, label=f"System: {name}", meta={"task": task.name})


def _from_process() -> Actor:
    argv = sys.argv
    if len(argv) > 1 and argv[0].endswith("manage.py"):
        return Actor(label=f"System: manage.py {argv[1]}", meta={"command": argv[1]})
    return Actor()


def current_actor() -> Actor:
    """The actor events written now are attributed to (see the module docstring)."""
    explicit = _explicit.get()
    if explicit is not None:
        return explicit
    job = _from_job()
    if job is not None:
        request = _request.get()
        return replace(job, request_id=request_id_of(request)) if request is not None else job
    request = _request.get()
    if request is not None:
        return _from_request(request)
    return _from_celery() or _from_process()


# ---- middleware --------------------------------------------------------------------------------


def _request_id(request: HttpRequest) -> str:
    given = request.headers.get(REQUEST_ID_HEADER, "")
    return given if _REQUEST_ID.match(given) else uuid.uuid4().hex


class AuditContextMiddleware:
    """Request id + the request as audit context for the whole request (install after
    ``AuthenticationMiddleware``)."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        request_id = _request_id(request)
        request.request_id = request_id  # type: ignore[attr-defined]
        token = _request.set(request)
        try:
            with structlog.contextvars.bound_contextvars(request_id=request_id):
                response = self.get_response(request)
        finally:
            _request.reset(token)
        response[REQUEST_ID_HEADER] = request_id
        return response
