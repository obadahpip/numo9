"""Line helpers (D-01-T02): item defaults flowing into a document line.

``apply_item(line, item, side)`` sets ``line.item`` and copies the item's defaults the line
doesn't have yet — description (else the item's name), unit price and account for the side
(``sales`` or ``purchase``). The tax code is not copied here: the item's tax key is the item step
of the place-of-supply precedence (G-02, ``numo9.tax.supply_context``), resolved per document
date. Values the person already typed are kept unless ``replace`` (picking another item replaces
what the previous item filled in).
"""

from __future__ import annotations

from typing import Any

SALES = "sales"
PURCHASE = "purchase"


def apply_item(line: Any, item: Any, side: str, *, replace: bool = False) -> Any:
    if side not in (SALES, PURCHASE):
        raise ValueError(f"Unknown side {side!r}.")
    line.item = item
    if item is None:
        return line
    if replace or not line.description:
        line.description = item.description or item.name
    price = item.default_price(side)
    if price is not None and (replace or not line.unit_price):
        line.unit_price = price
    account = item.sales_account if side == SALES else item.purchase_account
    if account is not None and (replace or line.account_id is None):
        line.account = account
    return line
