"""Journal approval notifications (C-04-T13): who hears about a submitted or decided journal.

Placeholders until C-04-T13 wires them to the notification service (A-07).
"""

from __future__ import annotations

from typing import Any


def journal_submitted(entry: Any, submitter: Any) -> None:
    """A journal was submitted for approval: the people who may approve it hear about it."""


def journal_decided(entry: Any, round_: Any) -> None:
    """A journal was approved (and posted) or sent back: its author hears about it."""
