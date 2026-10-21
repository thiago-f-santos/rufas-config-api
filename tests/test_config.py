from pathlib import Path

from rufas_config_api.config import Settings

ENV_NAMES = (
    "NASA_POWER_BASE_URL",
    "NASA_TIMEOUT_SECONDS",
    "NASA_POWER_LAG_DAYS",
    "SOIL_CATALOG_PATH",
    "SOIL_MAX_RINGS",
    "DATABASE_URL",
    "SOIL_MAX_DISTANCE_KM",
    "SOIL_WARNING_DISTANCE_KM",
)


def test_defaults_point_to_public_nasa_power(monkeypatch):
    for name in ENV_NAMES:
        monkeypatch.delenv(name, raising=False)

    settings = Settings()

    assert settings.nasa_power_base_url == "https://power.larc.nasa.gov"
    assert settings.nasa_timeout_seconds == 60.0
    assert settings.nasa_power_lag_days == 7


def test_soil_defaults(monkeypatch):
    for name in ENV_NAMES:
        monkeypatch.delenv(name, raising=False)

    settings = Settings()

    assert settings.soil_catalog_path == Path("data/soil/soil_catalog.sqlite")
    assert settings.soil_max_rings == 80


def test_values_are_read_from_environment(monkeypatch):
    monkeypatch.setenv("NASA_POWER_BASE_URL", "https://power.test")
    monkeypatch.setenv("NASA_TIMEOUT_SECONDS", "5")
    monkeypatch.setenv("NASA_POWER_LAG_DAYS", "3")
    monkeypatch.setenv("SOIL_CATALOG_PATH", "/tmp/catalog.sqlite")
    monkeypatch.setenv("SOIL_MAX_RINGS", "12")

    settings = Settings()

    assert settings.nasa_power_base_url == "https://power.test"
    assert settings.nasa_timeout_seconds == 5.0
    assert settings.nasa_power_lag_days == 3
    assert settings.soil_catalog_path == Path("/tmp/catalog.sqlite")
    assert settings.soil_max_rings == 12


def test_soil_database_settings_defaults(monkeypatch):
    for name in ENV_NAMES:
        monkeypatch.delenv(name, raising=False)

    settings = Settings()
    assert (
        settings.database_url
        == "postgresql+asyncpg://postgres:postgres@localhost:5432/rufas_config"
    )
    assert settings.soil_max_distance_km == 300.0
    assert settings.soil_warning_distance_km == 50.0


def test_soil_database_settings_env(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost:5432/custom_db")
    monkeypatch.setenv("SOIL_MAX_DISTANCE_KM", "150.0")
    monkeypatch.setenv("SOIL_WARNING_DISTANCE_KM", "25.0")

    settings = Settings()

    assert settings.database_url == "postgresql+asyncpg://user:pass@localhost:5432/custom_db"
    assert settings.soil_max_distance_km == 150.0
    assert settings.soil_warning_distance_km == 25.0
