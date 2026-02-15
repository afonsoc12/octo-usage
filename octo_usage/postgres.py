import os
from contextlib import contextmanager

import psycopg
from psycopg import conninfo
from psycopg.rows import dict_row

from .dataclasses import ElectricityConsumption
from .logging_config import get_logger

logger = get_logger(__name__)


class PostgresDB:
    """PostgreSQL database connection handler using raw SQL with dataclasses.

    Implements the Raw+DC pattern for type-safe database operations without an ORM.
    """

    def __init__(self):
        """Initialize PostgreSQL connection handler.

        Attempts to connect using DATABASE_URL if available,
        otherwise builds connection string from individual environment variables.
        """
        # Try to get connection string from DATABASE_URL first
        connection_string = os.getenv("DATABASE_URL")

        # If DATABASE_URL not set, build from individual variables
        if not connection_string:
            host = os.getenv("POSTGRES_HOST", "localhost")
            port = os.getenv("POSTGRES_PORT", "5432")
            user = os.getenv("POSTGRES_USER", "octopus")
            password = os.getenv("POSTGRES_PASSWORD", "octopus")
            dbname = os.getenv("POSTGRES_DB", "octopus_energy")

            # Use psycopg's conninfo to properly handle special characters in password
            connection_string = conninfo.make_conninfo(
                dbname=dbname,
                user=user,
                password=password,
                host=host,
                port=int(port),
            )
            logger.debug(
                f"Built connection string from individual variables: host={host}, port={port}, user={user}, db={dbname}"
            )
        else:
            logger.debug("Using DATABASE_URL connection string")

        self.connection_string = connection_string

        try:
            # Test connection
            with psycopg.connect(self.connection_string):
                logger.info("Successfully connected to PostgreSQL")
        except Exception as e:
            logger.error(f"Unable to connect to PostgreSQL: {e}", exc_info=True)
            raise

    @contextmanager
    def get_connection(self):
        """Context manager for database connections.

        Yields:
            psycopg connection object
        """
        conn = psycopg.connect(self.connection_string)
        try:
            yield conn
        finally:
            conn.close()

    def create_tables(self):
        """Create all tables defined in dataclass schema."""
        logger.debug("Creating database tables")
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(ElectricityConsumption.CREATE_TABLE_SQL)
                conn.commit()
        logger.info("Database tables created successfully")

    def insert_consumption(self, consumption: ElectricityConsumption) -> ElectricityConsumption:
        """Insert or update a single consumption record using upsert.

        Args:
            consumption: ElectricityConsumption dataclass instance

        Returns:
            The consumption object with id and created_at populated from database
        """
        logger.debug(
            f"Inserting consumption record: mpan={consumption.mpan}, "
            f"meter_sn={consumption.meter_sn}, interval={consumption.interval_start}"
        )
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                values = consumption.to_insert_values()
                cur.execute(ElectricityConsumption.UPSERT_SQL, values)
                result = cur.fetchone()

                if result:
                    consumption.id = result[0]
                    consumption.created_at = result[1]
                    logger.debug(f"Record inserted with id={consumption.id}")

                conn.commit()

        return consumption

    def insert_consumptions_batch(self, consumptions: list[ElectricityConsumption]) -> None:
        """Insert or update multiple consumption records in batch.

        Args:
            consumptions: List of ElectricityConsumption dataclass instances
        """
        if not consumptions:
            logger.warning("No consumptions provided for batch insert")
            return

        logger.debug(f"Starting batch insert of {len(consumptions)} records")
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                # Prepare values for batch insert
                values = [c.to_insert_values() for c in consumptions]

                # Use executemany for efficient batch insert
                cur.executemany(ElectricityConsumption.UPSERT_SQL, values)
                conn.commit()

        logger.info(f"Successfully inserted/updated {len(consumptions)} consumption records")

    def get_all_consumptions(self) -> list[ElectricityConsumption]:
        """Fetch all consumption records.

        Returns:
            List of ElectricityConsumption dataclass instances
        """
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(ElectricityConsumption.SELECT_ALL_SQL)
                rows = cur.fetchall()

        return [ElectricityConsumption.from_row(row) for row in rows]

    def get_consumptions_by_mpan(self, mpan: str) -> list[ElectricityConsumption]:
        """Fetch all consumption records for a specific MPAN.

        Args:
            mpan: Meter Point Administration Number (13 characters)

        Returns:
            List of ElectricityConsumption dataclass instances
        """
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(ElectricityConsumption.SELECT_BY_MPAN_SQL, (mpan,))
                rows = cur.fetchall()

        return [ElectricityConsumption.from_row(row) for row in rows]

    def get_consumptions_by_period(self, mpan: str, period_from: str, period_to: str) -> list[ElectricityConsumption]:
        """Fetch consumption records for a specific MPAN and time period.

        Args:
            mpan: Meter Point Administration Number
            period_from: ISO 8601 datetime string (inclusive)
            period_to: ISO 8601 datetime string (exclusive)

        Returns:
            List of ElectricityConsumption dataclass instances
        """
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(ElectricityConsumption.SELECT_BY_PERIOD_SQL, (mpan, period_from, period_to))
                rows = cur.fetchall()

        return [ElectricityConsumption.from_row(row) for row in rows]

    def delete_consumption(self, consumption_id: int) -> bool:
        """Delete a consumption record by ID.

        Args:
            consumption_id: Primary key ID

        Returns:
            True if record was deleted, False if not found
        """
        logger.debug(f"Deleting consumption record with id={consumption_id}")
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM electricity_consumption WHERE id = %s;", (consumption_id,))
                conn.commit()
                deleted = cur.rowcount > 0
                if deleted:
                    logger.debug(f"Record id={consumption_id} deleted successfully")
                else:
                    logger.debug(f"Record id={consumption_id} not found")
                return deleted

    def get_latest_consumption_timestamp(self, mpan: str) -> str | None:
        """Get the latest consumption timestamp for a given MPAN.

        Used for inferring the period_from when using --infer flag.

        Args:
            mpan: Meter Point Administration Number

        Returns:
            ISO 8601 formatted timestamp string of the latest interval_end, or None if no data exists
        """
        query = "SELECT MAX(interval_end) as latest FROM electricity_consumption WHERE mpan = %s;"

        with self.get_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (mpan,))
                result = cur.fetchone()

        if result and result["latest"]:
            latest_timestamp = result["latest"]
            # Convert to ISO 8601 format with Z suffix for API compatibility
            # The timestamp from DB is already timezone-aware, so just use isoformat()
            iso_timestamp = latest_timestamp.isoformat().replace("+00:00", "Z")
            logger.debug(f"Latest consumption timestamp for MPAN {mpan}: {iso_timestamp}")
            return iso_timestamp

        logger.debug(f"No consumption data found for MPAN {mpan}")
        return None

    def get_daily_aggregations(self, mpan: str) -> list[dict]:
        """Get daily aggregated consumption data.

        Args:
            mpan: Meter Point Administration Number

        Returns:
            List of dictionaries with daily aggregation data
        """
        query = """
            SELECT
                DATE(interval_start) as date,
                SUM(consumption) as total_consumption,
                COUNT(*) as reading_count,
                MIN(interval_start) as first_reading,
                MAX(interval_end) as last_reading,
                unit
            FROM electricity_consumption
            WHERE mpan = %s
            GROUP BY DATE(interval_start), unit
            ORDER BY DATE(interval_start) DESC;
        """

        with self.get_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (mpan,))
                return cur.fetchall()
