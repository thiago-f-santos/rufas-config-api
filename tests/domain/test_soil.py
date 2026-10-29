import pytest

from rufas_config_api.domain.soil import SoilMatch, SoilProfileDomain


def test_soil_profile_domain_instantiation():
    profile = SoilProfileDomain(
        id="profile_1",
        name="Latossolo Vermelho",
        latitude=-15.78,
        longitude=-47.93,
        h3_cell="86754e647ffffff",
        soil_data={"layers": [{"depth": 20, "sand": 40.0}]},
        provenance={"source": "EMBRAPA"},
    )

    assert profile.id == "profile_1"
    assert profile.name == "Latossolo Vermelho"
    assert profile.latitude == -15.78
    assert profile.longitude == -47.93
    assert profile.h3_cell == "86754e647ffffff"
    assert profile.soil_data == {"layers": [{"depth": 20, "sand": 40.0}]}
    assert profile.provenance == {"source": "EMBRAPA"}

    with pytest.raises((AttributeError, TypeError)):
        profile.name = "New Name"  # type: ignore[misc]


def test_soil_match_instantiation_and_defaults():
    profile = SoilProfileDomain(
        id="profile_1",
        name="Latossolo Vermelho",
        latitude=-15.78,
        longitude=-47.93,
        h3_cell="86754e647ffffff",
        soil_data={},
        provenance={},
    )

    match = SoilMatch(
        profile=profile,
        distance_km=12.5,
        request_cell="86754e647ffffff",
        match_type="exact",
    )

    assert match.profile == profile
    assert match.distance_km == 12.5
    assert match.request_cell == "86754e647ffffff"
    assert match.match_type == "exact"
    assert match.warning is None

    with pytest.raises((AttributeError, TypeError)):
        match.distance_km = 0.0  # type: ignore[misc]


def test_soil_match_with_warning():
    profile = SoilProfileDomain(
        id="profile_1",
        name="Latossolo Vermelho",
        latitude=-15.78,
        longitude=-47.93,
        h3_cell="86754e647ffffff",
        soil_data={},
        provenance={},
    )

    match = SoilMatch(
        profile=profile,
        distance_km=65.2,
        request_cell="86754e640ffffff",
        match_type="fallback_nearest",
        warning="Selected nearest profile is 65.2 km away (> 50.0 km threshold)",
    )

    assert match.match_type == "fallback_nearest"
    assert match.warning == "Selected nearest profile is 65.2 km away (> 50.0 km threshold)"
