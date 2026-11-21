"""V-04-T02 — dashboard widget provider registry + interface.

Acceptance: registering a provider exposes its widget (key, title, kind, figures); unregistering
removes it; an unknown kind is refused; a widget can be limited to some viewers; widgets come in
their order; a provider that raises answers ``error`` for its widget only.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from numo9.workspace import dashboard
from numo9.workspace.dashboard import (
    ALL,
    COUNT,
    DashboardContext,
    Widget,
    WidgetAnswer,
    answer_all,
    register_widget,
    unregister_widget,
)
from tests.workspace_helpers import member, practice, user

pytestmark = pytest.mark.django_db


@pytest.fixture
def ctx() -> DashboardContext:
    firm = practice("Abuodeh CPA")
    ada = user("ada@cpa.ca", name="Ada")
    return DashboardContext(
        user=ada, practice=firm, member=member(firm, ada, role="practice_admin"), scope=ALL
    )


@pytest.fixture
def isolated(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setattr(dashboard, "_widgets", {})
    yield


def test_registering_a_provider_exposes_its_widget(ctx: DashboardContext, isolated: None) -> None:
    register_widget(
        Widget(
            "test.count", "Test count", COUNT, lambda c: WidgetAnswer(count=7, filters={"x": ["y"]})
        )
    )
    (only,) = answer_all(ctx)
    assert only == {
        "key": "test.count",
        "title": "Test count",
        "description": "",
        "kind": "count",
        "status": "ok",
        "count": 7,
        "filters": {"x": ["y"]},
        "href": "",
        "items": [],
    }
    unregister_widget("test.count")
    assert answer_all(ctx) == []


def test_unknown_kind_is_refused(isolated: None) -> None:
    with pytest.raises(ValueError, match="Unknown widget kind"):
        register_widget(Widget("bad", "Bad", "pie", lambda c: WidgetAnswer()))


def test_order_and_visibility(ctx: DashboardContext, isolated: None) -> None:
    register_widget(Widget("b", "B", COUNT, lambda c: WidgetAnswer(count=1), order=20))
    register_widget(Widget("a", "A", COUNT, lambda c: WidgetAnswer(count=1), order=10))
    register_widget(
        Widget("hidden", "H", COUNT, lambda c: WidgetAnswer(count=1), visible=lambda c: False)
    )
    assert [w["key"] for w in answer_all(ctx)] == ["a", "b"]


def test_a_failing_provider_fails_only_its_widget(ctx: DashboardContext, isolated: None) -> None:
    def broken(c: DashboardContext) -> WidgetAnswer:
        raise RuntimeError("database gone")

    register_widget(Widget("ok", "OK", COUNT, lambda c: WidgetAnswer(count=0), order=1))
    register_widget(Widget("broken", "Broken", COUNT, broken, order=2))
    ok, failed = answer_all(ctx)
    assert (ok["status"], ok["count"]) == ("ok", 0)
    assert (failed["status"], failed["count"]) == ("error", None)
