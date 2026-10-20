# rufas-config-api

Generates input files for the [RuFaS](https://github.com/RuminantFarmSystems/RuFaS) simulator
from geographic coordinates. Responses are zip packages consumed by RuFaS' `RemoteDataAdapter`.

## Running

```bash
uv sync
uv run python -m rufas_config_api.providers.soil.index   # builds data/soil/soil_catalog.sqlite
uv run uvicorn rufas_config_api.main:app --reload
```

The API refuses to start if the soil catalog (`SOIL_CATALOG_PATH`) is missing; the error
message shows the command above. **Regenerate the index after changing `data/soil/`.**
The Docker image builds the index during `docker build`.

Or with Docker:

```bash
docker build -t rufas-config-api .
docker run --rm -p 8000:8000 rufas-config-api
```

Interactive docs: http://localhost:8000/docs

## Usage

```bash
curl -o inputs.zip \
  "http://localhost:8000/inputs?latitude=-16.36&longitude=-49.49&start_year=2015&end_year=2020&include=weather"
```

| Parameter | Description |
|---|---|
| `latitude`, `longitude` | Decimal degrees |
| `start_year`, `end_year` | Inclusive range; `start_year >= 1981`, `end_year <=` current year |
| `include` | Repeatable provider name (`weather`, `soil`). Omit to get every provider |

| Provider | File | Source |
|---|---|---|
| `weather` | `weather.csv` | NASA POWER daily point API |
| `soil` | `soil.json` | Nearest curated profile in the soil catalog (`data/soil/`) |

The package contains one file per provider, plus `manifest.json`
(SHA-256 of every file) and `provenance.json` (request, upstream query and versions).
For the current year, data ends `NASA_POWER_LAG_DAYS` before today.

### Soil

The soil catalog covers **Goiás and the Distrito Federal (GO+DF)**, as H3 cells at
resolution 6. For a point inside the coverage, the API returns the `soil.json` of the
nearest profile (H3 ring search, then great-circle distance), byte for byte as stored in
`data/soil/profiles/<id>/soil.json`. `provenance.json` records the profile id, its location,
the distance and the profile's own provenance. The `soil` provider ignores the years.

A point outside the coverage is rejected with HTTP 422:

```json
{"detail": {"message": "Location is outside the soil catalog coverage (GO+DF)",
            "latitude": -12.97, "longitude": -38.5, "coverage": "GO+DF"}}
```

The catalog is a SQLite file generated from `data/soil/` (profiles plus
`coverage_go_df_res6.json`) and is not versioned:

```bash
uv run python -m rufas_config_api.providers.soil.index \
  --data-dir data/soil --output data/soil/soil_catalog.sqlite
```

Regenerate the index after changing `data/soil/`.

## Configuration

| Variable | Default |
|---|---|
| `NASA_POWER_BASE_URL` | `https://power.larc.nasa.gov` |
| `NASA_TIMEOUT_SECONDS` | `60` |
| `NASA_POWER_LAG_DAYS` | `7` |
| `SOIL_CATALOG_PATH` | `data/soil/soil_catalog.sqlite` |
| `SOIL_MAX_RINGS` | `80` (H3 rings searched before giving up) |

## Development

```bash
uv run pytest --cov=rufas_config_api --cov-report=term-missing
uv run pytest -m integration   # hits the real NASA POWER API
uv run ruff check . && uv run ruff format --check .
```

### Adding a provider

Implement the `InputProvider` protocol (`providers/base.py`): a `name` and an async
`build(location, period) -> ProviderResult`. Register it in `api/dependencies.py:get_registry`.
