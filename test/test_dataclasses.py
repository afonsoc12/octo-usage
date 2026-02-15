from datetime import datetime

import pytest

from octo_usage.dataclasses import ElectricityConsumption


class TestElectricityConsumption:
    """Test the ElectricityConsumption dataclass with Raw+DC pattern methods."""

    @pytest.fixture
    def sample_data(self):
        """Sample dictionary data as might come from API."""
        return {
            "mpan": "1234567890123",
            "meter_sn": "METER123456",
            "consumption": 0.5,
            "interval_start": datetime(2023, 1, 15, 23, 30),
            "interval_end": datetime(2023, 1, 16, 0, 0),
            "unit": "kWh",
        }

    @pytest.fixture
    def sample_instance(self, sample_data):
        """Create a sample ElectricityConsumption instance."""
        return ElectricityConsumption(**sample_data)

    def test_create_instance(self, sample_instance):
        """Test creating an ElectricityConsumption instance."""
        assert sample_instance.mpan == "1234567890123"
        assert sample_instance.meter_sn == "METER123456"
        assert sample_instance.consumption == 0.5
        assert sample_instance.unit == "kWh"

    def test_from_dict(self, sample_data):
        """Test creating instance from dictionary using from_dict method."""
        instance = ElectricityConsumption.from_dict(sample_data)
        assert instance.mpan == sample_data["mpan"]
        assert instance.meter_sn == sample_data["meter_sn"]
        assert instance.consumption == sample_data["consumption"]

    def test_from_dict_with_serial_number_alias(self):
        """Test from_dict handles serial_number as alias for meter_sn."""
        data = {
            "mpan": "1234567890123",
            "serial_number": "METER123456",  # Alternative key
            "consumption": 0.5,
            "interval_start": datetime(2023, 1, 15, 23, 30),
            "interval_end": datetime(2023, 1, 16, 0, 0),
            "unit": "kWh",
        }
        instance = ElectricityConsumption.from_dict(data)
        assert instance.meter_sn == "METER123456"

    def test_to_dict(self, sample_instance):
        """Test converting instance to dictionary."""
        result = sample_instance.to_dict()
        assert result["mpan"] == "1234567890123"
        assert result["meter_sn"] == "METER123456"
        assert result["consumption"] == 0.5
        assert result["unit"] == "kWh"

    def test_to_insert_values(self, sample_instance):
        """Test converting instance to tuple for INSERT statement."""
        result = sample_instance.to_insert_values()
        assert isinstance(result, tuple)
        assert result[0] == "1234567890123"  # mpan
        assert result[1] == "METER123456"  # meter_sn
        assert result[2] == 0.5  # consumption

    def test_from_row(self):
        """Test creating instance from database row tuple."""
        # Simulating a tuple from database cursor:
        # (id, mpan, meter_sn, consumption, interval_start, interval_end, unit, created_at)
        row = (
            123,  # id
            "1234567890123",  # mpan
            "METER123456",  # meter_sn
            0.5,  # consumption
            datetime(2023, 1, 15, 23, 30),  # interval_start
            datetime(2023, 1, 16, 0, 0),  # interval_end
            "kWh",  # unit
            datetime(2023, 1, 16, 12, 0),  # created_at
        )

        instance = ElectricityConsumption.from_row(row)
        assert instance.id == 123
        assert instance.mpan == "1234567890123"
        assert instance.meter_sn == "METER123456"
        assert instance.consumption == 0.5
        assert instance.unit == "kWh"
        assert instance.created_at == datetime(2023, 1, 16, 12, 0)

    def test_default_unit(self):
        """Test that unit defaults to kWh."""
        instance = ElectricityConsumption(
            mpan="1234567890123",
            meter_sn="METER123456",
            consumption=0.5,
            interval_start=datetime(2023, 1, 15, 23, 30),
            interval_end=datetime(2023, 1, 16, 0, 0),
        )
        assert instance.unit == "kWh"

    def test_sql_queries_exist(self):
        """Test that SQL query constants are defined."""
        assert ElectricityConsumption.CREATE_TABLE_SQL is not None
        assert ElectricityConsumption.UPSERT_SQL is not None
        assert ElectricityConsumption.SELECT_ALL_SQL is not None
        assert ElectricityConsumption.SELECT_BY_MPAN_SQL is not None
        assert ElectricityConsumption.SELECT_BY_PERIOD_SQL is not None
