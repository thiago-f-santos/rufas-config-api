from rufas_config_api.config import Settings


def test_defaults_point_to_public_nasa_power(monkeypatch):
    for name in ("NASA_POWER_BASE_URL", "NASA_TIMEOUT_SECONDS", "NASA_POWER_LAG_DAYS"):
        monkeypatch.delenv(name, raising=False)

    settings = Settings()

    assert settings.nasa_power_base_url == "https://power.larc.nasa.gov"
    assert settings.nasa_timeout_seconds == 60.0
    assert settings.nasa_power_lag_days == 7


def test_values_are_read_from_environment(monkeypatch):
    monkeypatch.setenv("NASA_POWER_BASE_URL", "https://power.test")
    monkeypatch.setenv("NASA_TIMEOUT_SECONDS", "5")
    monkeypatch.setenv("NASA_POWER_LAG_DAYS", "3")

    settings = Settings()

    assert settings.nasa_power_base_url == "https://power.test"
    assert settings.nasa_timeout_seconds == 5.0
    assert settings.nasa_power_lag_days == 3
