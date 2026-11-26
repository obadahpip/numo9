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

