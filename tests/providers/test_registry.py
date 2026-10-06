import pytest

from rufas_config_api.domain import Location, Period, ProviderResult
from rufas_config_api.errors import UnknownProviderError
from rufas_config_api.providers import ProviderRegistry


class StubProvider:
    def __init__(self, name: str) -> None:
        self.name = name

    async def build(self, location: Location, period: Period) -> ProviderResult:
        return ProviderResult(self.name, (), {})


WEATHER = StubProvider("weather")
SOIL = StubProvider("soil")
REGISTRY = ProviderRegistry([WEATHER, SOIL])


def test_empty_include_resolves_every_provider():
    assert REGISTRY.resolve([]) == [WEATHER, SOIL]


def test_include_selects_providers_in_requested_order_without_duplicates():
    assert REGISTRY.resolve(["soil", "weather", "soil"]) == [SOIL, WEATHER]


def test_unknown_names_are_reported_with_available_ones():
    with pytest.raises(UnknownProviderError) as raised:
        REGISTRY.resolve(["weather", "animal"])

    assert raised.value.unknown == ["animal"]
    assert raised.value.available == ["weather", "soil"]
