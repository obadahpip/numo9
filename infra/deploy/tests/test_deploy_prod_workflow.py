"""Static checks for .github/workflows/deploy-prod.yml (S-01-T13).

    python3 infra/deploy/tests/test_deploy_prod_workflow.py      (needs PyYAML)

Guards the properties the approval gate relies on, so a later edit cannot quietly remove them.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[3]
WORKFLOW = ROOT / ".github" / "workflows" / "deploy-prod.yml"


def load() -> dict[str, Any]:
    data = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    # PyYAML (YAML 1.1) reads the key `on` as boolean True.
    data["on"] = data.pop(True, data.get("on"))
    return data


def checks(wf: dict[str, Any]) -> list[tuple[str, bool]]:
    jobs = wf["jobs"]
    resolve, deploy = jobs["resolve"], jobs["deploy"]
    on = wf["on"]
    deploy_text = yaml.safe_dump(deploy)
    other_jobs_text = yaml.safe_dump({k: v for k, v in jobs.items() if k != "deploy"})
    dispatch_inputs = on["workflow_dispatch"]["inputs"]
    return [
        ("triggers are exactly workflow_run + workflow_dispatch", set(on) == {"workflow_run", "workflow_dispatch"}),
        (
            "workflow_run follows 'Deploy staging' completions",
            on["workflow_run"]["workflows"] == ["Deploy staging"] and on["workflow_run"]["types"] == ["completed"],
        ),
        ("no push/tag trigger (production is never deployed directly from a tag push)", "push" not in on),
        ("dispatch requires a tag input", dispatch_inputs["tag"]["required"] is True),
        (
            "dispatch dry_run is boolean, default false",
            dispatch_inputs["dry_run"]["type"] == "boolean" and dispatch_inputs["dry_run"]["default"] is False,
        ),
        ("workflow-level permissions are read-only", wf["permissions"] == {"contents": "read"}),
        (
            "single production deploy at a time, never cancelled",
            wf["concurrency"]["group"] == "deploy-production" and wf["concurrency"]["cancel-in-progress"] is False,
        ),
        (
            "deploy job runs in environment 'production'",
            isinstance(deploy.get("environment"), dict) and deploy["environment"].get("name") == "production",
        ),
        (
            "deploy job needs resolve and is gated on its decision",
            deploy["needs"] == "resolve" and deploy["if"] == "needs.resolve.outputs.deploy == 'true'",
        ),
        ("resolve job has no environment (nothing waits before the checks)", "environment" not in resolve),
        (
            "production secrets are referenced only inside the gated deploy job",
            "secrets.PRODUCTION_" in deploy_text and "secrets.PRODUCTION_" not in other_jobs_text,
        ),
        (
            "production variables are referenced only inside the gated deploy job",
            "vars.PRODUCTION_" not in other_jobs_text,
        ),
        (
            "deploy job cannot write packages or contents",
            deploy["permissions"] == {"contents": "read", "packages": "read"},
        ),
        (
            "every remote step is skipped on dry run",
            all(
                "DRY_RUN != 'true'" in str(step.get("if", ""))
                for step in deploy["steps"]
                if re.search(r"\b(ssh|scp)\b", str(step.get("run", "")))
                and "install -m 700" not in str(step.get("run", ""))
            )
            and any("ssh production" in str(s.get("run", "")) for s in deploy["steps"]),
        ),
        ("deploy uses the shared health-gated deploy.sh", "bash deploy.sh" in deploy_text),
        (
            "resolve delegates tag rules to resolve-release.sh",
            any("infra/deploy/resolve-release.sh" in str(s.get("run", "")) for s in resolve["steps"]),
        ),
        (
            "images are verified, not rebuilt",
            "imagetools inspect" in other_jobs_text and "build-push-action" not in yaml.safe_dump(wf),
        ),
        (
            "tag must be on main and healthy on staging",
            "merge-base --is-ancestor" in other_jobs_text and "environment=staging" in other_jobs_text,
        ),
    ]


def main() -> int:
    results = checks(load())
    for name, ok in results:
        print(f"{'PASS' if ok else 'FAIL'}  {name}")
    failed = sum(not ok for _, ok in results)
    print(f"\n{len(results) - failed}/{len(results)} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
