from collections.abc import Sequence

from rufas_config_api.errors.base import RufasConfigError


class InvalidPeriodError(RufasConfigError):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class UnknownProviderError(RufasConfigError):
    def __init__(self, unknown: Sequence[str], available: Sequence[str]) -> None:
        self.unknown = list(unknown)
        self.available = list(available)
        super().__init__(f"Unknown input providers: {', '.join(self.unknown)}")


class OutOfCoverageError(RufasConfigError):
    def __init__(self, latitude: float, longitude: float, coverage: str) -> None:
        self.latitude = latitude
        self.longitude = longitude
        self.coverage = coverage
        self.message = f"Location is outside the soil catalog coverage ({coverage})"
        super().__init__(self.message)


class NoProfileInRangeError(RufasConfigError):
    def __init__(self, latitude: float, longitude: float, max_distance_km: float) -> None:
        self.latitude = latitude
        self.longitude = longitude
        self.max_distance_km = max_distance_km
        super().__init__(
            f"No soil profile within {max_distance_km} km of ({latitude}, {longitude})"
        )
