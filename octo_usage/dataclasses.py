from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class ElectricityConsumption:
    """Electricity consumption for a time interval.

    Raw+DC pattern dataclass mapping to electricity_consumption table.
    Includes table creation SQL and row/dict conversion methods.
    """

    mpan: str
    meter_sn: str
    consumption: float
    interval_start: datetime
    interval_end: datetime
    unit: str = "kWh"
    id: int | None = None
    created_at: datetime | None = None

    # Table creation SQL
    CREATE_TABLE_SQL = """
        CREATE TABLE IF NOT EXISTS electricity_consumption (
            id BIGSERIAL PRIMARY KEY,
            mpan VARCHAR(13) NOT NULL,
            meter_sn VARCHAR(50) NOT NULL,
            consumption DECIMAL(10, 3) NOT NULL,
            interval_start TIMESTAMPTZ NOT NULL,
            interval_end TIMESTAMPTZ NOT NULL,
            unit VARCHAR(10) DEFAULT 'kWh',
            created_at TIMESTAMPTZ DEFAULT NOW(),
            CONSTRAINT unique_reading UNIQUE(mpan, meter_sn, interval_start)
        );

        CREATE INDEX IF NOT EXISTS idx_mpan_interval
            ON electricity_consumption(mpan, interval_start DESC);

        CREATE INDEX IF NOT EXISTS idx_meter_interval
            ON electricity_consumption(meter_sn, interval_start DESC);

        CREATE INDEX IF NOT EXISTS idx_interval_start
            ON electricity_consumption(interval_start DESC);
    """

    # Insert/upsert SQL
    UPSERT_SQL = """
        INSERT INTO electricity_consumption
        (mpan, meter_sn, consumption, interval_start, interval_end, unit)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (mpan, meter_sn, interval_start)
        DO UPDATE SET
            consumption = EXCLUDED.consumption,
            interval_end = EXCLUDED.interval_end,
            unit = EXCLUDED.unit
        RETURNING id, created_at;
    """

    SELECT_ALL_SQL = "SELECT * FROM electricity_consumption ORDER BY interval_start DESC;"

    SELECT_BY_MPAN_SQL = """
        SELECT * FROM electricity_consumption
        WHERE mpan = %s
        ORDER BY interval_start DESC;
    """

    SELECT_BY_PERIOD_SQL = """
        SELECT * FROM electricity_consumption
        WHERE mpan = %s AND interval_start >= %s AND interval_start < %s
        ORDER BY interval_start DESC;
    """

    @classmethod
    def from_row(cls, row: tuple) -> ElectricityConsumption:
        """Convert a database row tuple to dataclass instance.

        Args:
            row: Tuple from database cursor in order:
                 (id, mpan, meter_sn, consumption, interval_start, interval_end, unit, created_at)

        Returns:
            ElectricityConsumption instance
        """
        return cls(
            id=row[0],
            mpan=row[1],
            meter_sn=row[2],
            consumption=float(row[3]),
            interval_start=row[4],
            interval_end=row[5],
            unit=row[6],
            created_at=row[7],
        )

    @classmethod
    def from_dict(cls, data: dict) -> ElectricityConsumption:
        """Convert a dictionary to dataclass instance.

        Useful when converting from API responses or other dict sources.

        Args:
            data: Dictionary with consumption data

        Returns:
            ElectricityConsumption instance
        """
        return cls(
            mpan=data.get("mpan"),
            meter_sn=data.get("meter_sn") or data.get("serial_number"),
            consumption=float(data["consumption"]),
            interval_start=data["interval_start"],
            interval_end=data["interval_end"],
            unit=data.get("unit", "kWh"),
            id=data.get("id"),
            created_at=data.get("created_at"),
        )

    def to_dict(self) -> dict:
        """Convert dataclass to dictionary for storage/API responses.

        Returns:
            Dictionary representation of the dataclass
        """
        return {
            "id": self.id,
            "mpan": self.mpan,
            "meter_sn": self.meter_sn,
            "consumption": self.consumption,
            "interval_start": self.interval_start,
            "interval_end": self.interval_end,
            "unit": self.unit,
            "created_at": self.created_at,
        }

    def to_insert_values(self) -> tuple:
        """Convert to tuple of values for INSERT statement.

        Returns:
            Tuple of values in order: (mpan, meter_sn, consumption, interval_start, interval_end, unit)
        """
        return (self.mpan, self.meter_sn, self.consumption, self.interval_start, self.interval_end, self.unit)
