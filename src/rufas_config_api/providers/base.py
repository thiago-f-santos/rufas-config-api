from typing import Protocol

from rufas_config_api.domain import Location, Period, ProviderResult


class InputProvider(Protocol):
    name: str

    async def build(self, location: Location, period: Period) -> ProviderResult: ...
