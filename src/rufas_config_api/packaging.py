import hashlib
import io
import json
import zipfile
from collections.abc import Iterable, Sequence
from typing import Any

from rufas_config_api.clock import Clock, utc_now
from rufas_config_api.domain import Location, PackageFile, Period, ProviderResult

MANIFEST_FILE = "manifest.json"
PROVENANCE_FILE = "provenance.json"
PACKAGE_VERSION = "1"
SERVICE_NAME = "rufas-config-api"


class PackageBuilder:
    def __init__(self, service_version: str, clock: Clock = utc_now) -> None:
        self._service_version = service_version
        self._clock = clock

    def build(
        self,
        results: Sequence[ProviderResult],
        location: Location,
        period: Period | None = None,
    ) -> bytes:
        generated_at = self._clock().isoformat()
        provider_files = [file for result in results for file in result.files]
        provenance = PackageFile(
            PROVENANCE_FILE, _to_json(self._provenance(results, location, period, generated_at))
        )
        packaged = [*provider_files, provenance]
        manifest = PackageFile(MANIFEST_FILE, _to_json(_manifest(packaged, generated_at)))
        return _zip([*packaged, manifest])

    def _provenance(
        self,
        results: Sequence[ProviderResult],
        location: Location,
        period: Period | None,
        generated_at: str,
    ) -> dict[str, Any]:
        return {
            "generated_at": generated_at,
            "service": {"name": SERVICE_NAME, "version": self._service_version},
            "request": {
                "latitude": location.latitude,
                "longitude": location.longitude,
                "start_year": period.start.year if period is not None else None,
                "end_year": period.requested_end.year if period is not None else None,
                "include": [result.provider for result in results],
            },
            "providers": {result.provider: dict(result.provenance) for result in results},
        }


def _manifest(files: Iterable[PackageFile], generated_at: str) -> dict[str, Any]:
    return {
        "package_version": PACKAGE_VERSION,
        "generated_at": generated_at,
        "files": [
            {
                "path": file.path,
                "sha256": hashlib.sha256(file.content).hexdigest(),
                "bytes": len(file.content),
                "provider": file.provider,
            }
            for file in files
        ],
    }


def _to_json(document: dict[str, Any]) -> bytes:
    return json.dumps(document, indent=2, ensure_ascii=False).encode()


def _zip(files: Iterable[PackageFile]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for file in files:
            archive.writestr(file.path, file.content)
    return buffer.getvalue()
