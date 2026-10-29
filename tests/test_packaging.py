import hashlib
import io
import json
import zipfile
from datetime import UTC, date, datetime

from rufas_config_api.domain import Location, PackageFile, Period, ProviderResult
from rufas_config_api.packaging import PackageBuilder

GENERATED_AT = datetime(2026, 10, 5, 12, 0, tzinfo=UTC)
LOCATION = Location(-16.36, -49.49)
PERIOD = Period(date(2015, 1, 1), date(2026, 9, 28), date(2026, 12, 31))
WEATHER = ProviderResult(
    provider="weather",
    files=(PackageFile("weather.csv", b"year,jday\n2015,1\n", provider="weather"),),
    provenance={"source": "NASA POWER"},
)


def build_archive() -> zipfile.ZipFile:
    builder = PackageBuilder(service_version="0.1.0", clock=lambda: GENERATED_AT)
    return zipfile.ZipFile(io.BytesIO(builder.build([WEATHER], LOCATION, PERIOD)))


def test_archive_contains_provider_files_manifest_and_provenance():
    with build_archive() as archive:
        assert sorted(archive.namelist()) == ["manifest.json", "provenance.json", "weather.csv"]
        assert archive.read("weather.csv") == b"year,jday\n2015,1\n"


def test_manifest_hashes_match_archived_content():
    with build_archive() as archive:
        manifest = json.loads(archive.read("manifest.json"))
        assert manifest["package_version"] == "1"
        assert manifest["generated_at"] == "2026-10-05T12:00:00+00:00"
        assert [entry["path"] for entry in manifest["files"]] == ["weather.csv", "provenance.json"]
        for entry in manifest["files"]:
            content = archive.read(entry["path"])
            assert entry["sha256"] == hashlib.sha256(content).hexdigest()
            assert entry["bytes"] == len(content)
        assert [entry["provider"] for entry in manifest["files"]] == ["weather", None]


def test_provenance_echoes_request_and_provider_blocks():
    with build_archive() as archive:
        provenance = json.loads(archive.read("provenance.json"))

    assert provenance == {
        "generated_at": "2026-10-05T12:00:00+00:00",
        "service": {"name": "rufas-config-api", "version": "0.1.0"},
        "request": {
            "latitude": -16.36,
            "longitude": -49.49,
            "start_year": 2015,
            "end_year": 2026,
            "include": ["weather"],
        },
        "providers": {"weather": {"source": "NASA POWER"}},
    }


def test_provenance_handles_none_period():
    builder = PackageBuilder(service_version="0.1.0", clock=lambda: GENERATED_AT)
    archive_bytes = builder.build([WEATHER], LOCATION, period=None)
    with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
        provenance = json.loads(archive.read("provenance.json"))

    assert provenance["request"]["start_year"] is None
    assert provenance["request"]["end_year"] is None
