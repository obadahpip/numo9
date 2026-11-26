"""The rule plug-ins of the exceptions engine (K-09): ``base`` is the framework; each module
registers its rules on import (``load_rules`` imports them all, from ``AssuranceConfig.ready``)."""

from __future__ import annotations

import importlib

#: Rule modules, in catalogue order (docs/specs/assurance-rules.md).
RULE_MODULES: tuple[str, ...] = ("cash", "journals")


def load_rules() -> None:
    for name in RULE_MODULES:
        importlib.import_module(f"{__name__}.{name}")
