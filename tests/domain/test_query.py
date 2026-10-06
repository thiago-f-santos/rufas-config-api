from datetime import date

import pytest

from rufas_config_api.domain import Period
from rufas_config_api.errors import InvalidPeriodError

TODAY = date(2026, 10, 5)


def test_past_years_cover_full_calendar_years():
    period = Period.from_years(2015, 2020, today=TODAY, lag_days=7)

    assert period.start == date(2015, 1, 1)
    assert period.end == date(2020, 12, 31)
    assert not period.truncated


def test_current_year_ends_lag_days_before_today():
    period = Period.from_years(2025, 2026, today=TODAY, lag_days=7)

    assert period.end == date(2026, 9, 28)
    assert period.requested_end == date(2026, 12, 31)
    assert period.truncated


@pytest.mark.parametrize(
    ("start_year", "end_year", "message"),
    [
        (1980, 1990, "start_year must be >= 1981"),
        (2020, 2019, "end_year must be >= start_year"),
        (2020, 2027, "end_year must be <= 2026"),
    ],
)
def test_invalid_year_ranges_are_rejected(start_year, end_year, message):
    with pytest.raises(InvalidPeriodError, match=message):
        Period.from_years(start_year, end_year, today=TODAY, lag_days=7)


def test_rejects_period_without_available_days_yet():
    with pytest.raises(InvalidPeriodError, match="latest available day is 2025-12-29"):
        Period.from_years(2026, 2026, today=date(2026, 1, 5), lag_days=7)


def test_days_iterates_every_day_inclusive():
    period = Period(date(2024, 2, 28), date(2024, 3, 1), date(2024, 3, 1))

    assert list(period.days()) == [date(2024, 2, 28), date(2024, 2, 29), date(2024, 3, 1)]
