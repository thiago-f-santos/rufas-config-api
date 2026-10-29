from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from rufas_config_api.errors.base import RufasConfigError


@dataclass(frozen=True, slots=True)
class MissingValue:
    day: date
    variables: tuple[str, ...]


class MissingDataError(RufasConfigError):
    def __init__(self, missing: Sequence[MissingValue]) -> None:
        self.missing = list(missing)
        super().__init__(
            f"Upstream has no data for {len(self.missing)} day(s) in the requested period"
        )


class SoilCatalogUnavailableError(RufasConfigError):
    def __init__(self, path: Path, reason: str) -> None:
        self.path = path
        self.reason = reason
        super().__init__(f"Soil catalog {path} is unavailable: {reason}")


class SoilCatalogError(RufasConfigError):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message
