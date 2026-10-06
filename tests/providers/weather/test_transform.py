from datetime import date

import pytest

from rufas_config_api.domain import Period
from rufas_config_api.errors import MissingDataError, MissingValue, UpstreamError
from rufas_config_api.providers.weather.transform import to_csv, to_rufas_rows


def period(start: date, end: date) -> Period:
    return Period(start, end, end)


def test_csv_follows_rufas_layout(nasa_payload):
    day = date(2024, 1, 1)

    rows = to_rufas_rows(nasa_payload(day, day), period(day, day))

    assert to_csv(rows).decode().splitlines() == [
        "year,jday,precip,high,low,avg,Hday,irrigation",
        "2024,1,1.23,30.5,18.25,24.0,20.13,0",
    ]


def test_julian_day_reaches_366_in_leap_years(nasa_payload):
    start, end = date(2024, 12, 30), date(2024, 12, 31)

    rows = to_rufas_rows(nasa_payload(start, end), period(start, end))

    assert [row.as_csv_record()[:2] for row in rows] == [(2024, 365), (2024, 366)]


def test_rows_are_ordered_by_day_regardless_of_payload_order(nasa_payload):
    start, end = date(2024, 1, 1), date(2024, 1, 3)
    payload = nasa_payload(start, end)
    for series in payload["properties"]["parameter"].values():
        reversed_items = list(series.items())[::-1]
        series.clear()
        series.update(reversed_items)

    rows = to_rufas_rows(payload, period(start, end))

    assert [row.day for row in rows] == [date(2024, 1, 1), date(2024, 1, 2), date(2024, 1, 3)]


def test_fill_values_are_reported_together(nasa_payload):
    start, end = date(2026, 9, 27), date(2026, 9, 28)
    payload = nasa_payload(
        start, end, missing=[(start, "T2M"), (start, "T2M_MAX"), (end, "PRECTOTCORR")]
    )

    with pytest.raises(MissingDataError) as raised:
        to_rufas_rows(payload, period(start, end))

    assert raised.value.missing == [
        MissingValue(start, ("T2M_MAX", "T2M")),
        MissingValue(end, ("PRECTOTCORR",)),
    ]


def test_absent_parameter_is_an_upstream_error(nasa_payload):
    day = date(2024, 1, 1)
    payload = nasa_payload(day, day)
    del payload["properties"]["parameter"]["T2M"]

    with pytest.raises(UpstreamError, match="missing parameters: T2M"):
        to_rufas_rows(payload, period(day, day))


def test_absent_day_is_an_upstream_error(nasa_payload):
    day = date(2024, 1, 1)

    with pytest.raises(UpstreamError, match="no PRECTOTCORR value for 2024-01-02"):
        to_rufas_rows(nasa_payload(day, day), period(day, date(2024, 1, 2)))


def test_payload_without_parameter_section_is_an_upstream_error():
    day = date(2024, 1, 1)

    with pytest.raises(UpstreamError, match=r"properties\.parameter"):
        to_rufas_rows({"messages": ["boom"]}, period(day, day))
