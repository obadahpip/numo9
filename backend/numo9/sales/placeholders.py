"""Placeholders in recurring invoices (D-04-T03) — moved to ``numo9.documents.placeholders`` so
recurring bills (E-03) share them; this module keeps the sales import path."""

from __future__ import annotations

from numo9.documents.placeholders import NAMES, PATTERN, month_name, render, unknown, values

__all__ = ["NAMES", "PATTERN", "month_name", "render", "unknown", "values"]
