"""Fiscal years of an organisation (its year end ``fye_month`` / ``fye_day``, A-05).

``fiscal_year(settings, day)`` → ``(start, end)`` of the fiscal year containing ``day``; a year
end on a day the month doesn't have (29 February, 31 June…) is the month's last day.
"""

from __future__ import annotations

import calendar
import datetime as dt
from typing import Any


def _year_end(year: int, month: int, day: int) -> dt.date:
    return dt.date(year, month, min(day, calendar.monthrange(year, month)[1]))


def fiscal_year(settings: Any, day: dt.date) -> tuple[dt.date, dt.date]:
    month, last = int(settings.fye_month), int(settings.fye_day)
    end = _year_end(day.year, month, last)
    if day > end:
        end = _year_end(day.year + 1, month, last)
    previous = _year_end(end.year - 1, month, last)
    return previous + dt.timedelta(days=1), end
