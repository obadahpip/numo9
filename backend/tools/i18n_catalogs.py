"""Shared loaders for the frontend JSON catalogues and backend gettext (.po) catalogues."""

from __future__ import annotations

import ast
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_MESSAGES_DIR = REPO_ROOT / "frontend" / "messages"
BACKEND_LOCALE_DIR = REPO_ROOT / "backend" / "locale"

# Locale codes as used by each side.
FRONTEND_LOCALES = ("en-CA", "fr-CA")
BACKEND_LOCALES = ("en_CA", "fr_CA")
SOURCE_FRONTEND_LOCALE = "en-CA"
SOURCE_BACKEND_LOCALE = "en_CA"


def flatten(tree: dict[str, Any], prefix: str = "") -> dict[str, str]:
    """Flatten a nested catalogue {"a": {"b": "x"}} into {"a.b": "x"}."""
    flat: dict[str, str] = {}
    for key, value in tree.items():
        path = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            flat.update(flatten(value, path))
        elif isinstance(value, str):
            flat[path] = value
        else:
            raise ValueError(f"{path}: catalogue values must be strings or objects")
    return flat


def unflatten(flat: dict[str, str]) -> dict[str, Any]:
    """Inverse of flatten(); keys are sorted for stable diffs."""
    tree: dict[str, Any] = {}
    for path in sorted(flat):
        node = tree
        *parents, leaf = path.split(".")
        for part in parents:
            child = node.setdefault(part, {})
            if not isinstance(child, dict):
                raise ValueError(f"{path}: '{part}' is both a message and a group")
            node = child
        if leaf in node and isinstance(node[leaf], dict):
            raise ValueError(f"{path}: is both a message and a group")
        node[leaf] = flat[path]
    return tree


def load_json_catalogue(path: Path) -> dict[str, str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path}: catalogue root must be an object")
    return flatten(data)


def write_json_catalogue(path: Path, flat: dict[str, str]) -> None:
    text = json.dumps(unflatten(flat), ensure_ascii=False, indent=2) + "\n"
    path.write_text(text, encoding="utf-8")


@dataclass(frozen=True)
class PoEntry:
    msgctxt: str | None
    msgid: str
    msgid_plural: str | None
    msgstr: tuple[str, ...]

    @property
    def key(self) -> str:
        return f"{self.msgctxt}\x04{self.msgid}" if self.msgctxt else self.msgid


def _unquote(token: str) -> str:
    value = ast.literal_eval(token)
    if not isinstance(value, str):
        raise ValueError(f"not a string literal: {token}")
    return value


def parse_po(text: str) -> list[PoEntry]:
    """Parse a gettext .po file. Obsolete (#~) entries and the header are skipped."""
    entries: list[PoEntry] = []
    fields: dict[str, str] = {}
    current: str | None = None

    def flush() -> None:
        nonlocal fields, current
        if "msgid" in fields and fields["msgid"] != "":
            msgstr = tuple(fields[k] for k in sorted(f for f in fields if f.startswith("msgstr")))
            entries.append(
                PoEntry(
                    msgctxt=fields.get("msgctxt"),
                    msgid=fields["msgid"],
                    msgid_plural=fields.get("msgid_plural"),
                    msgstr=msgstr,
                )
            )
        fields, current = {}, None

    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            flush()
            continue
        if line.startswith("#"):
            continue
        if line.startswith('"'):
            if current is None:
                raise ValueError(f"continuation line without keyword: {raw!r}")
            fields[current] += _unquote(line)
            continue
        keyword, _, rest = line.partition(" ")
        if keyword == "msgctxt" or (keyword == "msgid" and "msgid" in fields):
            flush()
        current = keyword
        fields[current] = _unquote(rest.strip())
    flush()
    return entries


def load_po(path: Path) -> list[PoEntry]:
    return parse_po(path.read_text(encoding="utf-8"))
