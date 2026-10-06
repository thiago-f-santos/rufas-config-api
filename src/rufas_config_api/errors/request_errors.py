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
