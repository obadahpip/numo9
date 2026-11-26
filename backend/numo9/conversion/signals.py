"""Signals of the conversion (C-05-T14).

- ``opening_equity_missing`` — sent once a conversion is finalised **without any equity line**
  (after the transaction commits; receivers' errors are caught: ``send_robust``). Keyword
  arguments: ``organisation``, ``session`` (the ``ConversionSession``), ``finding`` (a
  ``numo9.conversion.exceptions.ConversionFinding``, code ``OPENING_EQUITY_MISSING``). The
  exceptions engine (K-09) connects to it; see ``numo9.conversion.exceptions`` for the providers
  it can also poll.
"""

from __future__ import annotations

from django.dispatch import Signal

opening_equity_missing = Signal()
