from collections.abc import Callable, Iterable
from datetime import date, timedelta
from typing import Any

import pytest

DEFAULT_VALUES = {
    "PRECTOTCORR": 1.234,
    "T2M_MAX": 30.5,
    "T2M_MIN": 18.25,
    "T2M": 24.0,
    "ALLSKY_SFC_SW_DWN": 20.126,
}
FILL_VALUE = -999.0

type NasaPayloadFactory = Callable[..., dict[str, Any]]


@pytest.fixture
def nasa_payload() -> NasaPayloadFactory:
    def build(start: date, end: date, missing: Iterable[tuple[date, str]] = ()) -> dict[str, Any]:
        missing_values = set(missing)
        days = [start + timedelta(days=n) for n in range((end - start).days + 1)]
        parameter = {
            name: {
                day.strftime("%Y%m%d"): FILL_VALUE if (day, name) in missing_values else value
                for day in days
            }
            for name, value in DEFAULT_VALUES.items()
        }
        return {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [-49.49, -16.36, 807.47]},
            "properties": {"parameter": parameter},
            "header": {
                "api": {"version": "v2.10.0", "name": "POWER Daily API"},
                "sources": ["FLASHFLUX", "GEOSIT", "POWER"],
                "fill_value": FILL_VALUE,
                "start": start.strftime("%Y%m%d"),
                "end": end.strftime("%Y%m%d"),
            },
            "messages": [],
        }

    return build
