from rufas_config_api.errors.base import RufasConfigError


class UpstreamError(RufasConfigError):
    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class UpstreamTimeoutError(UpstreamError):
    def __init__(self, timeout_seconds: float) -> None:
        super().__init__(f"NASA POWER did not respond within {timeout_seconds} seconds")
        self.timeout_seconds = timeout_seconds
