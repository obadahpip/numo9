"""Run a command inside a workspace directory, rewriting repo-relative file paths.

pre-commit invokes hooks from the repository root and passes repo-relative paths.
Tools such as eslint and mypy must run from their own workspace (frontend/, backend/)
so they pick up local config and dependencies.

Usage:
    python tools/precommit/run_in.py DIR CMD [ARGS...] [-- FILES...]

- DIR is relative to the repository root.
- CMD "python" resolves to the interpreter running this script (the hook's environment).
- Other commands are resolved with shutil.which (handles .cmd shims on Windows).
- FILES after "--" are converted to paths relative to DIR.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__, file=sys.stderr)
        return 2

    workdir = (REPO_ROOT / argv[0]).resolve()
    rest = argv[1:]
    if "--" in rest:
        split = rest.index("--")
        command, files = rest[:split], rest[split + 1 :]
    else:
        command, files = rest, []

    executable = command[0]
    if executable == "python":
        resolved: str | None = sys.executable
    else:
        resolved = shutil.which(executable)
    if resolved is None:
        print(f"run_in.py: command not found: {executable}", file=sys.stderr)
        return 127

    relative_files = [os.path.relpath(REPO_ROOT / f, workdir) for f in files]
    # Command comes from .pre-commit-config.yaml (trusted, committed config), not user input.
    completed = subprocess.run(  # noqa: S603
        [resolved, *command[1:], *relative_files], cwd=workdir, check=False
    )
    return completed.returncode


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
