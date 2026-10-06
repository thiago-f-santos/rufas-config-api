from collections.abc import Iterable, Sequence

from rufas_config_api.errors import UnknownProviderError
from rufas_config_api.providers.base import InputProvider


class ProviderRegistry:
    def __init__(self, providers: Iterable[InputProvider]) -> None:
        self._providers = {provider.name: provider for provider in providers}

    def available(self) -> list[str]:
        return list(self._providers)

    def resolve(self, include: Sequence[str]) -> list[InputProvider]:
        if not include:
            return list(self._providers.values())

        requested = list(dict.fromkeys(include))
        unknown = [name for name in requested if name not in self._providers]
        if unknown:
            raise UnknownProviderError(unknown, self.available())
        return [self._providers[name] for name in requested]
