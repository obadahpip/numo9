from typing import Any

from django.apps import AppConfig


class AssuranceConfig(AppConfig):
    """Exceptions engine (K-09): rule plug-ins over the books, findings with a workflow, proposed
    fixes as draft journals, the assurance score and the activity heatmap."""

    name = "numo9.assurance"
    label = "assurance"
    verbose_name = "Assurance"

    def ready(self) -> None:
        from .rules import load_rules

        load_rules()  # every rule module registers its rules (K-09-T04)

        # Incremental runs on posting (K-09-T05).
        from numo9.ledger.services import POSTED_HOOKS

        from .runner import posted_hook

        if posted_hook not in POSTED_HOOKS:
            POSTED_HOOKS.append(posted_hook)

        # Tenant sweep (A-01-T09): one finding per endpoint, each with its own subject.
        from numo9.tenancy.sweep import SWEEP_FACTORIES

        SWEEP_FACTORIES["assurance.ExceptionFinding"] = _sweep_finding


def _sweep_finding(organisation: Any) -> Any:
    import uuid

    from .models import ExceptionFinding

    finding = ExceptionFinding(
        organisation=organisation,
        rule_code="NEG_CASH",
        severity="critical",
        subject_type="ledger.Account",
        subject_id=str(uuid.uuid4()),
        subject_label="Sweep",
    )
    finding.save()
    return finding
