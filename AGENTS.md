# Octopus Usage - Agent Information

## Quick Summary

Fetch electricity consumption from Octopus Energy API and persist to PostgreSQL database.

**Tech Stack**: Python 3.14+, PostgreSQL, Click CLI, Raw SQL + Dataclasses pattern

## Tools & Commands

### Package Manager
- **Tool**: `uv` (manages Python environment and dependencies)
- **Config**: `pyproject.toml`, `uv.lock`

### Running the Application
```bash
uv run --env-file .env python -m octo_usage [FLAGS]
```

**CLI Flags**:
- `--period-start` - Start date (ISO 8601)
- `--period-end` - End date (ISO 8601)
- `--infer` - Infer start from latest stored data (default to 1970 if empty)
- `--dry-run` - Preview without database connection
- `--limit` - Limit records in dry-run mode

### Running Tests
```bash
uv run pytest [test_file.py] [options]
```

**Common options**:
- `-v` - Verbose output
- `-m "not integration"` - Skip integration tests
- `--tb=short` - Short traceback format

## CI/CD Checks

All checks from `.github/workflows/ci.yml`:

### Format Check
```bash
uv run ruff format --check
```
Verify code formatting without modifying files (use `uv run ruff format` to auto-fix).

### Lint & Import Check
```bash
uv run ruff check
```
Check for linting issues and import problems.

### Run Unit Tests
```bash
uv run pytest -m "not integration"
```
Run all tests except integration tests (integration tests require PostgreSQL).

## Project Structure

```
octo_usage/
├── __main__.py         # CLI entry point (Click)
├── octopus.py          # Octopus Energy API client
├── postgres.py         # PostgreSQL database layer
├── dataclasses.py      # ElectricityConsumption model with embedded SQL
├── logging_config.py   # Structured logging setup

test/
├── test_postgres.py    # Database integration tests
├── test_octopus.py     # API client tests
├── test_dataclasses.py # Data model tests
├── test_cli_infer.py   # CLI --infer flag tests
└── data/               # Test fixtures
```

## Core Components

### `octopus.py`
- Octopus Energy API client with pagination
- Converts API responses to `ElectricityConsumption` dataclasses

### `postgres.py`
- PostgreSQL connection management
- UPSERT operations (prevents duplicates)
- `get_latest_consumption_timestamp(mpan)` - Used for `--infer` flag

### `dataclasses.py`
- `ElectricityConsumption` model with embedded SQL schema and queries

### `__main__.py`
- Click CLI interface

## Database Schema

**Table**: `electricity_consumption`
- `id` - BIGSERIAL PRIMARY KEY
- `mpan` - VARCHAR(13)
- `meter_sn` - VARCHAR(50)
- `consumption` - DECIMAL(10, 3) kWh
- `interval_start` - TIMESTAMPTZ
- `interval_end` - TIMESTAMPTZ
- `unit` - VARCHAR(10)
- `created_at` - TIMESTAMPTZ

**Unique Constraint**: `(mpan, meter_sn, interval_start)`
**Indexes**: `idx_mpan_interval`, `idx_meter_interval`, `idx_interval_start`

## Environment Variables

**Required**:
- `OCTOPUS_API_KEY` - Octopus Energy API key
- `OCTOPUS_ELECTRICITY_MPAN` - Meter Point Administration Number
- `OCTOPUS_ELECTRICITY_SN` - Meter serial number

**Database** (use `DATABASE_URL` OR individual vars):
- `DATABASE_URL` - Full connection string (takes priority)
- OR: `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`

**Optional**:
- `LOG_LEVEL` - DEBUG, INFO (default), WARNING, ERROR
- `LOG_FORMAT` - text (default) or logfmt (structured)
- `TZ` - Timezone

## Design Pattern

**Raw+DC (Raw SQL + Dataclasses)**:
- Raw SQL queries for performance and control
- Dataclasses for type-safe data models
- No ORM overhead
- SQL constants embedded in dataclass definitions

## Key Features

- **Event Sourcing**: Each consumption record is immutable and traceable
- **Idempotent Operations**: UPSERT prevents duplicate data
- **Pagination Support**: Automatically handles large datasets
- **Timezone-Aware**: All timestamps stored as TIMESTAMPTZ
- **Dry-Run Mode**: Preview data without database connection
- **Infer Mode**: Automatically fetch from last stored timestamp
