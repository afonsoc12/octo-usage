# 🐙 octo-usage

---

> ⚡ Fetch electricity consumption from Octopus Energy API and persists it to PostgreSQL database.

> ⚠️ **Early Development** — Currently performs one-off data scrapes. Designed to be used with a cronjob or Kubernetes CronJob for periodic execution.

## 🎯 Overview

**octo-usage** is a Python application that automatically retrieves your electricity consumption data from the Octopus Energy API and stores it in a PostgreSQL database for analysis and tracking.

> 📌 **Note:** Due to how the Octopus Energy API works, consumption data is provided with a one-day delay. Data from the previous day becomes available sometime in the morning of the next day.

## 📋 Requirements

- 🐳 Docker
- ??PostgreSQL database
- 🔑 Octopus Energy API credentials

## 🚀 Quick Start

### Installation

Run the application using Docker:

```bash
docker run --rm \
  -e OCTOPUS_API_KEY="your-api-key-here" \
  -e OCTOPUS_ELECTRICITY_MPAN="your-mpan-number" \
  -e OCTOPUS_ELECTRICITY_SN="your-meter-sn" \
  -e DATABASE_URL="postgresql://user:password@host:5432/octo_usage" \
  ghcr.io/afonsoc12/octo-usage --help
```

## ⚙️ Configuration

Configure the application by setting the following environment variables:

| Variable | Description | Example                                          |
|----------|-------------|--------------------------------------------------|
| `OCTOPUS_API_KEY` | 🔐 Your Octopus Energy API key | `sk_live_...`                                    |
| `OCTOPUS_ELECTRICITY_MPAN` | 📍 Your electricity MPAN number | `<MPAN>`                                         |
| `OCTOPUS_ELECTRICITY_SN` | 🔢 Your electricity meter Serial Number | `<METER SN>`                                     |
| `DATABASE_URL` | 🐘 PostgreSQL connection string (optional) | `postgresql://user:password@localhost/octo_usage` |
| `POSTGRES_HOST` | 🐘 PostgreSQL host (if not using DATABASE_URL) | `localhost`                                      |
| `POSTGRES_PORT` | 🐘 PostgreSQL port (if not using DATABASE_URL) | `5432`                                           |
| `POSTGRES_USER` | 👤 PostgreSQL username (if not using DATABASE_URL) | `octopus`                                        |
| `POSTGRES_PASSWORD` | 🔐 PostgreSQL password (if not using DATABASE_URL) | `octopus`                                        |
| `POSTGRES_DB` | 📦 PostgreSQL database name (if not using DATABASE_URL) | `octopus_energy`                                 |
| `LOG_LEVEL` | 📊 Logging level (DEBUG, INFO, WARNING, ERROR) | `INFO`                                           |
| `LOG_FORMAT` | 📋 Log format (text or logfmt) | `logfmt`                                         |
| `TZ` | 🌍 Timezone | `Australia/Sydney`                               |

### 📝 Example with Environment File

Create a `.env` file:

```bash
OCTOPUS_API_KEY=your-api-key-here
OCTOPUS_ELECTRICITY_MPAN=your-mpan-number
OCTOPUS_ELECTRICITY_SN=your-meter-sn
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=octopus
POSTGRES_PASSWORD=octopus
POSTGRES_DB=octopus_energy
LOG_LEVEL=info
LOG_FORMAT=logfmt
TZ=Australia/Sydney
```

Then run:

```bash
docker run --rm --env-file .env ghcr.io/afonsoc12/octo-usage
```

## 🚩 CLI Flags

The application supports the following command-line flags:

| Flag | Type | Description | Example |
|------|------|-------------|---------|
| `--period-start` | DateTime | Start timestamp to fetch data (ISO 8601 format) | `2026-02-01T00:00:00Z` |
| `--period-end` | DateTime | End timestamp to fetch data (ISO 8601 format) | `2026-02-15T23:59:59Z` |
| `--infer` | Flag | Infer period_start from latest stored data (defaults to 1970 if no data exists) | `--infer` |
| `--dry-run` | Flag | Print records without storing to database (skips database connection) | `--dry-run` |
| `--limit` | Integer | Limit number of records to display in dry-run mode (default: show all) | `--limit 10` |

### 📝 Usage Examples

Fetch all consumption data and store in database:

```bash
docker run --rm --env-file .env ghcr.io/afonsoc12/octo-usage
```

Fetch data for a specific period:

```bash
docker run --rm --env-file .env ghcr.io/afonsoc12/octo-usage \
  --period-start 2026-02-01T00:00:00Z \
  --period-end 2026-02-15T23:59:59Z
```

Dry-run mode (view records without database storage):

```bash
docker run --rm --env-file .env ghcr.io/afonsoc12/octo-usage --dry-run
```

Dry-run mode with limit (show only first 10 records):

```bash
docker run --rm --env-file .env ghcr.io/afonsoc12/octo-usage --dry-run --limit 10
```

Infer mode (fetch from latest stored data or 1970 if empty):

```bash
docker run --rm --env-file .env ghcr.io/afonsoc12/octo-usage --infer
```

Combine --infer with --period-end to fetch from latest up to a specific date:

```bash
docker run --rm --env-file .env ghcr.io/afonsoc12/octo-usage \
  --infer \
  --period-end 2026-02-15
```

## 📄 License

---

**Copyright © 2023–2026 [Afonso Costa](https://github.com/afonsoc12)**

Licensed under the Apache License 2.0. See the [LICENSE](./LICENSE) file for details.
