"""Integration tests for PostgreSQL database layer."""

from datetime import UTC, datetime, timedelta

import pytest

from octo_usage.dataclasses import ElectricityConsumption
from octo_usage.postgres import PostgresDB

pytestmark = pytest.mark.integration


@pytest.fixture
def db():
    """Create a PostgresDB instance for testing."""
    return PostgresDB()


@pytest.fixture
def sample_consumption():
    """Create a sample ElectricityConsumption record."""
    return ElectricityConsumption(
        mpan="1234567890123",
        meter_sn="METER001",
        consumption=0.5,
        interval_start=datetime(2023, 1, 15, 23, 30, tzinfo=UTC),
        interval_end=datetime(2023, 1, 16, 0, 0, tzinfo=UTC),
        unit="kWh",
    )


@pytest.fixture
def sample_consumptions():
    """Create multiple sample ElectricityConsumption records."""
    start = datetime(2023, 1, 15, 0, 0, tzinfo=UTC)
    records = []
    for i in range(5):
        interval_start = start + timedelta(hours=i * 30)
        interval_end = interval_start + timedelta(minutes=30)
        records.append(
            ElectricityConsumption(
                mpan="1234567890123",
                meter_sn="METER001",
                consumption=0.5 + (i * 0.1),
                interval_start=interval_start,
                interval_end=interval_end,
                unit="kWh",
            )
        )
    return records


class TestPostgresDB:
    """Test PostgreSQL database operations."""

    def test_create_tables(self, db):
        """Test that tables are created successfully."""
        db.create_tables()

        with db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT EXISTS (SELECT FROM information_schema.tables "
                    "WHERE table_name = 'electricity_consumption');"
                )
                assert cur.fetchone()[0] is True

    def test_insert_consumption(self, db, sample_consumption):
        """Test inserting a single consumption record."""
        result = db.insert_consumption(sample_consumption)

        assert result.id is not None
        assert result.created_at is not None
        assert result.mpan == "1234567890123"
        assert result.consumption == 0.5

    def test_insert_consumption_upsert(self, db, sample_consumption):
        """Test that inserting the same record updates it."""
        # First insert
        result1 = db.insert_consumption(sample_consumption)
        id1 = result1.id

        # Update the consumption value
        sample_consumption.consumption = 0.75
        result2 = db.insert_consumption(sample_consumption)
        id2 = result2.id

        # Should be the same record (upsert behavior)
        assert id1 == id2
        # Verify the update
        records = db.get_all_consumptions()
        assert len(records) == 1
        assert records[0].consumption == 0.75

    def test_insert_consumptions_batch(self, db, sample_consumptions):
        """Test batch inserting multiple records."""
        db.insert_consumptions_batch(sample_consumptions)

        all_records = db.get_all_consumptions()
        assert len(all_records) == len(sample_consumptions)

    def test_get_all_consumptions(self, db, sample_consumptions):
        """Test fetching all consumption records."""
        db.insert_consumptions_batch(sample_consumptions)

        records = db.get_all_consumptions()

        assert len(records) == len(sample_consumptions)
        assert all(isinstance(r, ElectricityConsumption) for r in records)
        # Records should be in DESC order by interval_start
        assert records[0].interval_start > records[-1].interval_start

    def test_get_consumptions_by_mpan(self, db, sample_consumptions):
        """Test querying records by MPAN."""
        db.insert_consumptions_batch(sample_consumptions)

        records = db.get_consumptions_by_mpan("1234567890123")

        assert len(records) == len(sample_consumptions)
        assert all(r.mpan == "1234567890123" for r in records)

    def test_get_consumptions_by_mpan_empty(self, db):
        """Test querying by MPAN returns empty for nonexistent MPAN."""
        records = db.get_consumptions_by_mpan("9999999999999")

        assert len(records) == 0

    def test_get_consumptions_by_period(self, db, sample_consumptions):
        """Test querying records by time period."""
        db.insert_consumptions_batch(sample_consumptions)

        # Query for first 2 records
        period_from = sample_consumptions[0].interval_start
        period_to = sample_consumptions[2].interval_start

        records = db.get_consumptions_by_period("1234567890123", period_from.isoformat(), period_to.isoformat())

        # Should get records whose interval_start is in the range
        assert len(records) > 0
        assert all(period_from <= r.interval_start < period_to for r in records)

    def test_delete_consumption(self, db, sample_consumption):
        """Test deleting a consumption record."""
        # Insert a record
        result = db.insert_consumption(sample_consumption)
        record_id = result.id

        # Verify it exists
        records = db.get_all_consumptions()
        assert len(records) == 1

        # Delete it
        deleted = db.delete_consumption(record_id)
        assert deleted is True

        # Verify it's gone
        records = db.get_all_consumptions()
        assert len(records) == 0

    def test_delete_consumption_not_found(self, db):
        """Test deleting a nonexistent record returns False."""
        deleted = db.delete_consumption(999999)
        assert deleted is False

    def test_get_daily_aggregations(self, db):
        """Test getting daily aggregated consumption data."""
        # Insert records for 2 days
        base_date = datetime(2023, 1, 15, 0, 0)
        records = []

        for day in range(2):
            for hour in range(0, 24, 1):
                interval_start = base_date + timedelta(days=day, hours=hour)
                interval_end = interval_start + timedelta(hours=1)
                records.append(
                    ElectricityConsumption(
                        mpan="1234567890123",
                        meter_sn="METER001",
                        consumption=0.5,
                        interval_start=interval_start,
                        interval_end=interval_end,
                        unit="kWh",
                    )
                )

        db.insert_consumptions_batch(records)

        # Get daily aggregations
        aggregations = db.get_daily_aggregations("1234567890123")

        # Should have 2 days
        assert len(aggregations) == 2

        # Each day should have 24 readings
        for agg in aggregations:
            assert agg["reading_count"] == 24
            assert agg["total_consumption"] == pytest.approx(12.0)  # 24 * 0.5

    def test_conversion_to_from_row(self, db, sample_consumption):
        """Test dataclass conversion methods work with database rows."""
        # Insert and retrieve
        result = db.insert_consumption(sample_consumption)

        # Fetch the raw row
        with db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, mpan, meter_sn, consumption, interval_start, "
                    "interval_end, unit, created_at FROM electricity_consumption "
                    "WHERE id = %s;",
                    (result.id,),
                )
                row = cur.fetchone()

        # Convert back to dataclass
        restored = ElectricityConsumption.from_row(row)

        assert restored.id == result.id
        assert restored.mpan == sample_consumption.mpan
        assert restored.meter_sn == sample_consumption.meter_sn
        assert restored.consumption == sample_consumption.consumption
        assert restored.unit == sample_consumption.unit

    def test_unique_constraint(self, db):
        """Test that unique constraint on (mpan, meter_sn, interval_start) works."""
        consumption1 = ElectricityConsumption(
            mpan="1234567890123",
            meter_sn="METER001",
            consumption=0.5,
            interval_start=datetime(2023, 1, 15, 0, 0),
            interval_end=datetime(2023, 1, 15, 1, 0),
            unit="kWh",
        )

        consumption2 = ElectricityConsumption(
            mpan="1234567890123",
            meter_sn="METER001",
            consumption=0.6,
            interval_start=datetime(2023, 1, 15, 0, 0),  # Same start time
            interval_end=datetime(2023, 1, 15, 1, 0),
            unit="kWh",
        )

        db.insert_consumption(consumption1)
        db.insert_consumption(consumption2)

        # Should have updated the first record
        records = db.get_all_consumptions()
        assert len(records) == 1
        assert records[0].consumption == 0.6

    def test_indexes_created(self, db):
        """Test that indexes are created for query performance."""
        indexes = [
            "idx_mpan_interval",
            "idx_meter_interval",
            "idx_interval_start",
        ]

        with db.get_connection() as conn:
            with conn.cursor() as cur:
                for index_name in indexes:
                    cur.execute("SELECT EXISTS(SELECT 1 FROM pg_indexes WHERE indexname = %s);", (index_name,))
                    assert cur.fetchone()[0] is True

    def test_get_latest_consumption_timestamp_with_data(self, db, sample_consumptions):
        """Test getting the latest consumption timestamp when data exists."""
        # Insert sample data
        db.insert_consumptions_batch(sample_consumptions)

        # Get the latest timestamp
        latest = db.get_latest_consumption_timestamp("1234567890123")

        # Should return a valid ISO 8601 string with Z suffix
        assert latest is not None
        assert latest.endswith("Z")
        assert "T" in latest

        # The latest timestamp should be the interval_end of the last record
        # Records are inserted in order, so the last one has the latest interval_end
        expected = sample_consumptions[-1].interval_end.isoformat().replace("+00:00", "Z")
        assert latest == expected

    def test_get_latest_consumption_timestamp_no_data(self, db):
        """Test getting the latest consumption timestamp when no data exists."""
        # Query for a non-existent MPAN
        latest = db.get_latest_consumption_timestamp("9999999999999")

        # Should return None
        assert latest is None

    def test_get_latest_consumption_timestamp_multiple_mpans(self, db, sample_consumptions):
        """Test that get_latest_consumption_timestamp only returns data for the specified MPAN."""
        # Insert sample data for MPAN 1
        db.insert_consumptions_batch(sample_consumptions)

        # Insert sample data for MPAN 2 with more recent timestamps
        later_start = datetime(2023, 2, 15, 0, 0, tzinfo=UTC)
        later_records = []
        for i in range(3):
            interval_start = later_start + timedelta(hours=i * 30)
            interval_end = interval_start + timedelta(minutes=30)
            later_records.append(
                ElectricityConsumption(
                    mpan="9876543210123",  # Different MPAN
                    meter_sn="METER002",
                    consumption=0.7 + (i * 0.1),
                    interval_start=interval_start,
                    interval_end=interval_end,
                    unit="kWh",
                )
            )
        db.insert_consumptions_batch(later_records)

        # Get latest for MPAN 1 - should not include MPAN 2 data
        latest_mpan1 = db.get_latest_consumption_timestamp("1234567890123")
        latest_mpan2 = db.get_latest_consumption_timestamp("9876543210123")

        # MPAN 2 should have a later timestamp
        assert latest_mpan1 is not None
        assert latest_mpan2 is not None
        assert latest_mpan2 > latest_mpan1
