from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

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
