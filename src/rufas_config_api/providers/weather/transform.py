import csv
import io
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date
from typing import Any

from rufas_config_api.domain import Period
from rufas_config_api.errors import MissingDataError, MissingValue, UpstreamError

NASA_TO_RUFAS_COLUMNS: dict[str, str] = {
    "PRECTOTCORR": "precip",
    "T2M_MAX": "high",
    "T2M_MIN": "low",
    "T2M": "avg",
    "ALLSKY_SFC_SW_DWN": "Hday",
}
CSV_HEADER = ("year", "jday", *NASA_TO_RUFAS_COLUMNS.values(), "irrigation")
DEFAULT_FILL_VALUE = -999.0
DECIMALS = 2
RAINFED_IRRIGATION = 0

type Series = Mapping[str, Mapping[str, Any]]


@dataclass(frozen=True, slots=True)
class WeatherRow:
    day: date
    precip: float
    high: float
    low: float
    avg: float
    hday: float
    irrigation: int = RAINFED_IRRIGATION

    def as_csv_record(self) -> tuple[int | float, ...]:
        return (
            self.day.year,
            self.day.timetuple().tm_yday,
            self.precip,
            self.high,
            self.low,
            self.avg,
            self.hday,
            self.irrigation,
        )


def to_rufas_rows(payload: Mapping[str, Any], period: Period) -> list[WeatherRow]:
    series = _extract_series(payload)
    fill_value = (payload.get("header") or {}).get("fill_value", DEFAULT_FILL_VALUE)

    rows: list[WeatherRow] = []
    missing: list[MissingValue] = []
    for day in period.days():
        values = _read_day(series, day)
        absent = tuple(name for name, value in values.items() if value == fill_value)
        if absent:
            missing.append(MissingValue(day, absent))
        else:
            rows.append(_to_row(day, values))

    if missing:
        raise MissingDataError(missing)
    return rows


def to_csv(rows: Iterable[WeatherRow]) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(CSV_HEADER)
    writer.writerows(row.as_csv_record() for row in rows)
    return buffer.getvalue().encode()


def _extract_series(payload: Mapping[str, Any]) -> Series:
    try:
        series = payload["properties"]["parameter"]
    except (KeyError, TypeError) as error:
        raise UpstreamError("NASA POWER response has no properties.parameter section") from error

    absent = [name for name in NASA_TO_RUFAS_COLUMNS if name not in series]
    if absent:
        raise UpstreamError(f"NASA POWER response is missing parameters: {', '.join(absent)}")
    return series


def _read_day(series: Series, day: date) -> dict[str, float]:
    key = day.strftime("%Y%m%d")
    values: dict[str, float] = {}
    for name in NASA_TO_RUFAS_COLUMNS:
        try:
            values[name] = float(series[name][key])
        except (KeyError, TypeError, ValueError) as error:
            raise UpstreamError(
                f"NASA POWER response has no {name} value for {day.isoformat()}"
            ) from error
    return values


def _to_row(day: date, values: Mapping[str, float]) -> WeatherRow:
    rounded = {name: round(value, DECIMALS) for name, value in values.items()}
    return WeatherRow(
        day=day,
        precip=rounded["PRECTOTCORR"],
        high=rounded["T2M_MAX"],
        low=rounded["T2M_MIN"],
        avg=rounded["T2M"],
        hday=rounded["ALLSKY_SFC_SW_DWN"],
    )
