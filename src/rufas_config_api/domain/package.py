from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class PackageFile:
    path: str
    content: bytes
    provider: str | None = None


@dataclass(frozen=True, slots=True)
class ProviderResult:
    provider: str
    files: tuple[PackageFile, ...]
    provenance: Mapping[str, Any]
