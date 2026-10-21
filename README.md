# rufas-config-api

Generates input files for the [RuFaS](https://github.com/RuminantFarmSystems/RuFaS) simulator
from geographic coordinates. Responses are zip packages consumed by RuFaS' `RemoteDataAdapter`.

## Running

### Production / Local with PostgreSQL + PostGIS

```bash
uv sync
docker compose up -d db          # starts PostgreSQL 16 + PostGIS
uv run alembic upgrade head      # runs migrations and seeds v0 initial catalog
uv run uvicorn rufas_config_api.main:app --reload
```

Interactive docs: http://localhost:8000/docs

### Docker

```bash
docker build -t rufas-config-api .
docker run --rm -p 8000:8000 -e DATABASE_URL="postgresql+asyncpg://postgres:postgres@host.docker.internal:5432/rufas_config" rufas-config-api
```

## Usage

### Generating RuFaS Input Packages (`/inputs`)

```bash
# Weather + Soil (requires start_year and end_year for weather)
curl -o inputs.zip \
  "http://localhost:8000/inputs?latitude=-16.36&longitude=-49.49&start_year=2015&end_year=2020"

# Soil only (start_year and end_year are optional)
curl -o soil_only.zip \
  "http://localhost:8000/inputs?latitude=-16.36&longitude=-49.49&include=soil"
```

| Parameter | Description |
|---|---|
| `latitude`, `longitude` | Decimal degrees |
| `start_year`, `end_year` | Inclusive range; `start_year >= 1981`, `end_year <=` current year. Required when `weather` is included; optional when only requesting soil (`include=soil`). |
| `include` | Repeatable provider name (`weather`, `soil`). Omit to get every provider. |

| Provider | File | Source |
|---|---|---|
| `weather` | `weather.csv` | NASA POWER daily point API |
| `soil` | `soil.json` | Two-tier search (exact H3 cell match, then PostGIS KNN nearest fallback) |

The package contains one file per provider, plus `manifest.json`
(SHA-256 of every file) and `provenance.json` (request, upstream query and versions).
For the current year, weather data ends `NASA_POWER_LAG_DAYS` before today.

### Soil Provider & Catalog

The soil catalog covers **Goiás and the Distrito Federal (GO+DF)**, indexed as H3 cells at
resolution 6. When resolving soil for a coordinate within coverage:
1. **Tier 1 (Exact Match):** Checks if the coordinate's H3 cell is directly mapped to a profile (O(1) lookup).
2. **Tier 2 (Nearest Fallback):** If not directly mapped, searches for the nearest profile within `SOIL_MAX_DISTANCE_KM` (PostGIS KNN with spatial indexing). If the nearest profile is farther than `SOIL_WARNING_DISTANCE_KM`, a warning is included in `provenance.json`.

A point outside coverage is rejected with HTTP 422:

```json
{"detail": {"message": "Location is outside the soil catalog coverage (GO+DF)",
            "latitude": -12.97, "longitude": -38.5, "coverage": "GO+DF"}}
```

### Dynamic Soil Management (`/soils/profiles`)

The API exposes RESTful CRUD endpoints for dynamic profile management:

- `POST /soils/profiles`: Create a new soil profile. Validates soil layer physics (fraction sums, moisture ordering) and automatically indexes the H3 cell at resolution 6. Returns `409 Conflict` if the profile ID already exists.
- `GET /soils/profiles/{id}`: Retrieve a soil profile by ID.
- `PUT /soils/profiles/{id}`: Update profile metadata, coordinates, or soil layers. If coordinates move to a new H3 cell, the old cell mapping is unmapped and the new cell is mapped.
- `DELETE /soils/profiles/{id}`: Delete a profile. Associated cell mappings are automatically deleted via foreign key cascade.

## Configuration

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://postgres:postgres@localhost:5432/rufas_config` | Database connection URL (PostgreSQL + PostGIS for production; SQLite memory supported) |
| `SOIL_MAX_DISTANCE_KM` | `300.0` | Maximum distance (km) for fallback nearest-neighbor search |
| `SOIL_WARNING_DISTANCE_KM` | `50.0` | Distance threshold (km) beyond which a warning is attached |
| `NASA_POWER_BASE_URL` | `https://power.larc.nasa.gov` | NASA POWER base URL |
| `NASA_TIMEOUT_SECONDS` | `60` | HTTP timeout for NASA POWER requests |
| `NASA_POWER_LAG_DAYS` | `7` | Data lag days for current year weather queries |
| `SOIL_CATALOG_PATH` | `data/soil/soil_catalog.sqlite` | Path to static SQLite catalog (legacy fallback/seed) |
| `SOIL_MAX_RINGS` | `80` | Maximum H3 search rings in legacy SQLite catalog fallback |

## Development

Tests run **100% in-memory with zero Docker required** using SQLite:

```bash
uv run pytest                                                 # runs all unit/in-memory tests
uv run pytest --cov=rufas_config_api --cov-report=term-missing # with coverage report
uv run pytest -m integration                                  # hits external services / PostgreSQL if running
uv run ruff check . && uv run ruff format --check .          # linter & formatting check
```

### Adding a provider

Implement the `InputProvider` protocol (`providers/base.py`): a `name` and an async
`build(location, period) -> ProviderResult`. Register it in `api/dependencies.py:get_registry`.
