# rufas-config-api

Generates input files for the [RuFaS](https://github.com/RuminantFarmSystems/RuFaS) simulator
from geographic coordinates. Responses are zip packages consumed by RuFaS' `RemoteDataAdapter`.

## Running

```bash
uv sync
uv run uvicorn rufas_config_api.main:app --reload
```

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
| `include` | Repeatable provider name (`weather`). Omit to get every provider |

The package contains one file per provider (`weather.csv`), plus `manifest.json`
(SHA-256 of every file) and `provenance.json` (request, upstream query and versions).
For the current year, data ends `NASA_POWER_LAG_DAYS` before today.

## Configuration

| Variable | Default |
|---|---|
| `NASA_POWER_BASE_URL` | `https://power.larc.nasa.gov` |
| `NASA_TIMEOUT_SECONDS` | `60` |
| `NASA_POWER_LAG_DAYS` | `7` |

## Development

```bash
uv run pytest --cov=rufas_config_api --cov-report=term-missing
uv run pytest -m integration   # hits the real NASA POWER API
uv run ruff check . && uv run ruff format --check .
```

### Adding a provider

Implement the `InputProvider` protocol (`providers/base.py`): a `name` and an async
`build(location, period) -> ProviderResult`. Register it in `api/dependencies.py:get_registry`.
