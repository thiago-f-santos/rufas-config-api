from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Self

from rufas_config_api.errors import InvalidPeriodError

FIRST_AVAILABLE_YEAR = 1981


@dataclass(frozen=True, slots=True)
class Location:
    latitude: float
    longitude: float


@dataclass(frozen=True, slots=True)
class Period:
    start: date
    end: date
    requested_end: date

    @classmethod
    def from_years(cls, start_year: int, end_year: int, *, today: date, lag_days: int) -> Self:
        if start_year < FIRST_AVAILABLE_YEAR:
            raise InvalidPeriodError(f"start_year must be >= {FIRST_AVAILABLE_YEAR}")
        if end_year < start_year:
            raise InvalidPeriodError("end_year must be >= start_year")
        if end_year > today.year:
            raise InvalidPeriodError(f"end_year must be <= {today.year}")

        start = date(start_year, 1, 1)
        requested_end = date(end_year, 12, 31)
        latest_available = today - timedelta(days=lag_days)
        if latest_available < start:
            raise InvalidPeriodError(
                f"No data available yet for {start_year}; "
                f"latest available day is {latest_available.isoformat()}"
            )
        return cls(start, min(requested_end, latest_available), requested_end)

    @property
    def truncated(self) -> bool:
        return self.end < self.requested_end

    def days(self) -> Iterator[date]:
        for offset in range((self.end - self.start).days + 1):
            yield self.start + timedelta(days=offset)
