#!/usr/bin/env python3
"""CLI for octopus-api-consumer.

Execute with:
  $ uv run --env-file .env python -m octo_usage
  $ python -m octo_usage  # (if env vars already set)
"""

import os
from datetime import datetime

import click

from octo_usage.logging_config import get_logger, setup_logging
from octo_usage.octopus import Octopus
from octo_usage.postgres import PostgresDB

logger = get_logger(__name__)


@click.command()
@click.option(
    "--period-start",
    type=click.DateTime(),
    default=None,
    help="Start timestamp to fetch data (ISO 8601 format)",
)
@click.option(
    "--period-end",
    type=click.DateTime(),
    default=None,
    help="End timestamp to fetch data (ISO 8601 format)",
)
@click.option(
    "--infer",
    is_flag=True,
    help="Infer period_start from latest stored data (defaults to 1970 if no data exists)",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Print records without storing to database (skips database connection)",
)
@click.option(
    "--limit",
    type=int,
    default=None,
    help="Limit number of records to display in dry-run mode (default: show all)",
)
def main(period_start, period_end, infer, dry_run, limit):  # noqa: C901
    """Fetch electricity consumption data from Octopus Energy API and store in PostgreSQL."""
    # Initialize logging
    setup_logging()

    # Handle --infer flag to automatically determine period_start
    if infer and not period_start:
        logger.info("Inferring period_start from latest stored data...")
        try:
            db = PostgresDB()
            mpan = os.getenv("OCTOPUS_ELECTRICITY_MPAN")

            try:
                # Try to get latest timestamp from database
                latest_timestamp = db.get_latest_consumption_timestamp(mpan)

                if latest_timestamp:
                    logger.info(f"Found latest consumption data at {latest_timestamp}, fetching from that point onwards")
                    # Parse the ISO timestamp string (format: 2026-02-12T01:00:00Z)
                    period_start = datetime.fromisoformat(latest_timestamp.replace("Z", "+00:00"))
                else:
                    logger.info("No consumption data found in database, fetching from 1970-01-01")
                    period_start = None  # This will default to 1970-01-01 in Octopus class
            except Exception as table_error:
                # Table doesn't exist - create it and start from beginning
                if "UndefinedTable" in str(type(table_error).__name__) or "does not exist" in str(table_error):
                    logger.info("Table does not exist yet, creating it and fetching from 1970-01-01")
                    db.create_tables()
                    period_start = None
                else:
                    raise
        except Exception as e:
            logger.error(f"Error inferring period_start: {e}", exc_info=True)
            raise

    # Convert naive datetimes to UTC-aware for API compatibility
    if period_start:
        period_start_str = period_start.isoformat().replace("+00:00", "") + "Z"
    else:
        period_start_str = None

    if period_end:
        period_end_str = period_end.isoformat().replace("+00:00", "") + "Z"
    else:
        period_end_str = None

    logger.debug(f"Fetching consumption from {period_start_str or 'start'} to {period_end_str or 'now'}")

    logger.info("Fetching consumption data from Octopus Energy API...")
    octopus = Octopus()

    if dry_run:
        # Dry-run: fetch all and display
        consumptions = octopus.consumption(
            period_from=period_start_str,
            period_to=period_end_str,
        )

        if not consumptions:
            logger.warning("No consumption data received from Octopus API")
            return

        logger.info(
            f"Fetched {len(consumptions)} consumption records from "
            f"{period_start_str or 'start'} to {period_end_str or 'now'}"
        )

        logger.info("Dry-run mode: Displaying records without database storage")
        logger.info("=" * 80)

        # Determine how many records to display
        records_to_show = consumptions[:limit] if limit else consumptions

        for i, cons in enumerate(records_to_show, 1):
            # Handle both datetime objects and string timestamps
            start_str = (
                cons.interval_start.isoformat()
                if hasattr(cons.interval_start, "isoformat")
                else str(cons.interval_start)
            )
            end_str = (
                cons.interval_end.isoformat() if hasattr(cons.interval_end, "isoformat") else str(cons.interval_end)
            )

            logger.info(
                f"[{i:4d}] MPAN: {cons.mpan} | Meter: {cons.meter_sn} | "
                f"Consumption: {cons.consumption:>6.3f} {cons.unit} | "
                f"Interval: {start_str} → {end_str}"
            )

        logger.info("=" * 80)
        if limit and len(consumptions) > limit:
            logger.info(f"Showing {limit} of {len(consumptions)} records (use --limit to adjust)")
        else:
            logger.info(f"Total records displayed: {len(records_to_show)}")
    else:
        # Non-dry-run: stream pages to database as they arrive
        logger.info("Connecting to PostgreSQL database...")
        db = PostgresDB()
        db.create_tables()

        total_records = 0

        # Define per-page callback to insert each page as it arrives
        def insert_page(page_consumptions):
            nonlocal total_records
            total_records += len(page_consumptions)
            logger.info(
                f"Inserting {len(page_consumptions)} consumption records "
                f"from this page (total so far: {total_records})..."
            )
            db.insert_consumptions_batch(page_consumptions)

        # Fetch with per-page callback
        logger.info("Fetching and storing consumption records...")
        consumptions = octopus.consumption(period_from=period_start_str, period_to=period_end_str, on_page=insert_page)

        if not consumptions:
            logger.warning("No consumption data received from Octopus API")
            return

        logger.info(
            f"Fetched {len(consumptions)} consumption records from "
            f"{period_start_str or 'start'} to {period_end_str or 'now'}"
        )
        logger.info("Successfully stored all consumption data in PostgreSQL")


if __name__ == "__main__":
    main()
