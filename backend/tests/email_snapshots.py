"""Snapshot files of rendered emails (A-07-T04, T11): tests/snapshots/email/<name>.<lang>.<part>.

``NUMO9_UPDATE_SNAPSHOTS=1 pytest …`` writes the files; otherwise a rendered email must equal its
snapshot byte for byte (a template change is reviewed as a snapshot diff).
"""

from __future__ import annotations

import os
from pathlib import Path

SNAPSHOTS = Path(__file__).parent / "snapshots" / "email"


def assert_snapshot(name: str, content: str) -> None:
    path = SNAPSHOTS / name
    if os.environ.get("NUMO9_UPDATE_SNAPSHOTS") == "1" or not path.exists():
        if os.environ.get("CI") and not path.exists():
            raise AssertionError(f"missing snapshot {path}: run with NUMO9_UPDATE_SNAPSHOTS=1")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    expected = path.read_text(encoding="utf-8")
    assert content == expected, f"{name} differs from its snapshot (NUMO9_UPDATE_SNAPSHOTS=1)"
