"""Holiday calendar and business-day roll (G-03a-T06).

``HolidayCalendar`` reads ``data/holidays_ca.json``: by year, the **federal** statutory holidays
(``CA`` — the CRA's non-business days) and each province's or territory's own, with a holiday
on a weekend observed on the next weekday. The data is the rule: a new year is added to the file
each autumn, with no code change.

``calendar.roll(day, jurisdictions)`` — a due date on a Saturday, Sunday or holiday of any of the
``jurisdictions`` moves to the next business day (CRA and Revenu Québec practice: a return or
payment received then is on time). GST/HST due dates roll on federal holidays; QST due dates on
federal and Quebec holidays (``jurisdictions_for``). A year missing from the data rolls on
weekends only (``known(year)`` says whether the year is loaded).
"""

from __future__ import annotations

import datetime as dt
import json
from collections.abc import Iterable
from functools import cache
from pathlib import Path

DATA = Path(__file__).parent / "data" / "holidays_ca.json"
FEDERAL = "CA"


class HolidayCalendar:
    def __init__(self, years: dict[str, dict[str, dict[str, str]]]) -> None:
        self._years = {
            int(year): {
                place: {dt.date.fromisoformat(day): name for name, day in days.items()}
                for place, days in places.items()
            }
            for year, places in years.items()
        }

    def known(self, year: int) -> bool:
        return year in self._years

    def holidays(self, year: int, jurisdictions: Iterable[str] = (FEDERAL,)) -> dict[dt.date, str]:
        places = self._years.get(year, {})
        out: dict[dt.date, str] = {}
        for place in jurisdictions:
            out.update(places.get(place, {}))
        return out

    def is_business_day(self, day: dt.date, jurisdictions: Iterable[str] = (FEDERAL,)) -> bool:
        return day.weekday() < 5 and day not in self.holidays(day.year, tuple(jurisdictions))

    def roll(self, day: dt.date, jurisdictions: Iterable[str] = (FEDERAL,)) -> dt.date:
        """``day`` itself when it is a business day, else the next one."""
        places = tuple(jurisdictions)
        while not self.is_business_day(day, places):
            day += dt.timedelta(days=1)
        return day


@cache
def calendar() -> HolidayCalendar:
    return HolidayCalendar(json.loads(DATA.read_text(encoding="utf-8"))["years"])


def jurisdictions_for(registration_type: str) -> tuple[str, ...]:
    """Whose holidays roll a registration's due dates: QST adds Quebec's."""
    return (FEDERAL, "QC") if registration_type == "qst" else (FEDERAL,)
