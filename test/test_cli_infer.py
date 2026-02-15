"""Unit tests for CLI --infer flag functionality."""

import os
from datetime import datetime, timedelta
from unittest import mock

import pytest
from click.testing import CliRunner

from octo_usage.__main__ import main
from octo_usage.dataclasses import ElectricityConsumption


class TestCliInferFlag:
    """Test the --infer flag in the CLI."""

    @pytest.fixture
    def runner(self):
        """Create a Click CLI test runner."""
        return CliRunner()

    @pytest.fixture
    def mock_env(self):
        """Mock environment variables."""
        return {
            "OCTOPUS_API_KEY": "sk_test_123",
            "OCTOPUS_ELECTRICITY_MPAN": "1234567890123",
            "OCTOPUS_ELECTRICITY_SN": "METER001",
            "POSTGRES_HOST": "localhost",
            "POSTGRES_PORT": "5432",
            "POSTGRES_USER": "test",
            "POSTGRES_PASSWORD": "test",
            "POSTGRES_DB": "test_db",
            "LOG_LEVEL": "INFO",
            "LOG_FORMAT": "text",
        }

    def test_infer_flag_with_existing_data(self, runner, mock_env):
        """Test --infer flag when data exists in the database."""
        latest_timestamp = "2026-02-12T01:00:00Z"

        with mock.patch.dict(os.environ, mock_env):
            with mock.patch("octo_usage.__main__.PostgresDB") as mock_db_class:
                with mock.patch("octo_usage.__main__.Octopus") as mock_octopus_class:
                    # Setup mock database
                    mock_db_instance = mock.Mock()
                    mock_db_class.return_value = mock_db_instance
                    mock_db_instance.get_latest_consumption_timestamp.return_value = latest_timestamp

                    # Setup mock Octopus API
                    mock_octopus_instance = mock.Mock()
                    mock_octopus_class.return_value = mock_octopus_instance
                    mock_octopus_instance.consumption.return_value = []

                    # Run CLI with --infer and --dry-run
                    result = runner.invoke(main, ["--infer", "--dry-run"])
                    assert result.exit_code == 0

                    # Check that the database method was called
                    mock_db_instance.get_latest_consumption_timestamp.assert_called_once_with("1234567890123")

                    # Check that consumption was called with the inferred timestamp
                    mock_octopus_instance.consumption.assert_called_once()
                    call_kwargs = mock_octopus_instance.consumption.call_args[1]
                    assert call_kwargs["period_from"] == latest_timestamp

    def test_infer_flag_with_no_data(self, runner, mock_env):
        """Test --infer flag when no data exists in the database."""
        with mock.patch.dict(os.environ, mock_env):
            with mock.patch("octo_usage.__main__.PostgresDB") as mock_db_class:
                with mock.patch("octo_usage.__main__.Octopus") as mock_octopus_class:
                    # Setup mock database - return None (no data)
                    mock_db_instance = mock.Mock()
                    mock_db_class.return_value = mock_db_instance
                    mock_db_instance.get_latest_consumption_timestamp.return_value = None

                    # Setup mock Octopus API
                    mock_octopus_instance = mock.Mock()
                    mock_octopus_class.return_value = mock_octopus_instance
                    mock_octopus_instance.consumption.return_value = []

                    # Run CLI with --infer and --dry-run
                    result = runner.invoke(main, ["--infer", "--dry-run"])
                    assert result.exit_code == 0

                    # Check that consumption was called with None (defaults to 1970)
                    mock_octopus_instance.consumption.assert_called_once()
                    call_kwargs = mock_octopus_instance.consumption.call_args[1]
                    assert call_kwargs["period_from"] is None

    def test_infer_with_explicit_period_start(self, runner, mock_env):
        """Test that explicit --period-start takes precedence over --infer."""
        with mock.patch.dict(os.environ, mock_env):
            with mock.patch("octo_usage.__main__.PostgresDB") as mock_db_class:
                with mock.patch("octo_usage.__main__.Octopus") as mock_octopus_class:
                    # Setup mocks
                    mock_db_instance = mock.Mock()
                    mock_db_class.return_value = mock_db_instance
                    mock_octopus_instance = mock.Mock()
                    mock_octopus_class.return_value = mock_octopus_instance
                    mock_octopus_instance.consumption.return_value = []

                    # Run CLI with both --infer and --period-start
                    result = runner.invoke(main, ["--infer", "--dry-run", "--period-start", "2026-02-01T00:00:00"])
                    assert result.exit_code == 0

                    # Database method should NOT be called when explicit period_start is given
                    mock_db_instance.get_latest_consumption_timestamp.assert_not_called()

                    # Check that consumption was called with the explicit period
                    mock_octopus_instance.consumption.assert_called_once()
                    call_kwargs = mock_octopus_instance.consumption.call_args[1]
                    assert "2026-02-01T00:00:00Z" in call_kwargs["period_from"]

    def test_infer_formats_timestamp_correctly(self, runner, mock_env):
        """Test that --infer correctly formats the timestamp for the API."""
        # This timestamp simulates what comes from the database
        db_timestamp = "2026-02-12T01:00:00Z"

        with mock.patch.dict(os.environ, mock_env):
            with mock.patch("octo_usage.__main__.PostgresDB") as mock_db_class:
                with mock.patch("octo_usage.__main__.Octopus") as mock_octopus_class:
                    mock_db_instance = mock.Mock()
                    mock_db_class.return_value = mock_db_instance
                    mock_db_instance.get_latest_consumption_timestamp.return_value = db_timestamp

                    mock_octopus_instance = mock.Mock()
                    mock_octopus_class.return_value = mock_octopus_instance
                    mock_octopus_instance.consumption.return_value = []

                    result = runner.invoke(main, ["--infer", "--dry-run"])
                    assert result.exit_code == 0

                    # Verify the timestamp is passed correctly to the API
                    mock_octopus_instance.consumption.assert_called_once()
                    call_kwargs = mock_octopus_instance.consumption.call_args[1]
                    # Should have single Z, not double timezone indicators
                    assert call_kwargs["period_from"] == "2026-02-12T01:00:00Z"
                    assert "+00:00Z" not in call_kwargs["period_from"]

    def test_infer_with_limit_flag(self, runner, mock_env):
        """Test --infer combined with --limit flag."""
        db_timestamp = "2026-02-12T01:00:00Z"
        sample_consumptions = [
            ElectricityConsumption(
                mpan="1234567890123",
                meter_sn="METER001",
                consumption=0.5 + (i * 0.1),
                interval_start=datetime.fromisoformat("2026-02-12T01:00:00+00:00") + timedelta(hours=i),
                interval_end=datetime.fromisoformat("2026-02-12T01:00:00+00:00") + timedelta(hours=i + 1),
                unit="kWh",
            )
            for i in range(5)
        ]

        with mock.patch.dict(os.environ, mock_env):
            with mock.patch("octo_usage.__main__.PostgresDB") as mock_db_class:
                with mock.patch("octo_usage.__main__.Octopus") as mock_octopus_class:
                    mock_db_instance = mock.Mock()
                    mock_db_class.return_value = mock_db_instance
                    mock_db_instance.get_latest_consumption_timestamp.return_value = db_timestamp

                    mock_octopus_instance = mock.Mock()
                    mock_octopus_class.return_value = mock_octopus_instance
                    mock_octopus_instance.consumption.return_value = sample_consumptions

                    # Run with --infer, --dry-run, and --limit
                    result = runner.invoke(main, ["--infer", "--dry-run", "--limit", "3"])

                    # Should succeed and display limited records
                    assert result.exit_code == 0
                    # Should show 3 records in output
                    output_lines = result.output.split("\n")
                    consumption_lines = [
                        line for line in output_lines if "[" in line and "]" in line and "MPAN" in line
                    ]
                    assert len(consumption_lines) == 3

    def test_infer_with_period_end(self, runner, mock_env):
        """Test --infer combined with --period-end flag."""
        db_timestamp = "2026-02-12T01:00:00Z"

        with mock.patch.dict(os.environ, mock_env):
            with mock.patch("octo_usage.__main__.PostgresDB") as mock_db_class:
                with mock.patch("octo_usage.__main__.Octopus") as mock_octopus_class:
                    mock_db_instance = mock.Mock()
                    mock_db_class.return_value = mock_db_instance
                    mock_db_instance.get_latest_consumption_timestamp.return_value = db_timestamp

                    mock_octopus_instance = mock.Mock()
                    mock_octopus_class.return_value = mock_octopus_instance
                    mock_octopus_instance.consumption.return_value = []

                    # Run with --infer and --period-end
                    result = runner.invoke(main, ["--infer", "--dry-run", "--period-end", "2026-02-15T00:00:00"])
                    assert result.exit_code == 0

                    # Check that both period_from and period_to are set
                    mock_octopus_instance.consumption.assert_called_once()
                    call_kwargs = mock_octopus_instance.consumption.call_args[1]
                    assert call_kwargs["period_from"] == db_timestamp
                    assert call_kwargs["period_to"] == "2026-02-15T00:00:00Z"

    def test_infer_with_missing_table(self, runner, mock_env):
        """Test --infer flag when table doesn't exist yet (should create it and start from 1970)."""
        with mock.patch.dict(os.environ, mock_env):
            with mock.patch("octo_usage.__main__.PostgresDB") as mock_db_class:
                with mock.patch("octo_usage.__main__.Octopus") as mock_octopus_class:
                    mock_db_instance = mock.Mock()
                    mock_db_class.return_value = mock_db_instance

                    # Simulate table not existing
                    mock_db_instance.get_latest_consumption_timestamp.side_effect = Exception(
                        'psycopg.errors.UndefinedTable: relation "electricity_consumption" does not exist'
                    )

                    mock_octopus_instance = mock.Mock()
                    mock_octopus_class.return_value = mock_octopus_instance
                    mock_octopus_instance.consumption.return_value = []

                    # Run with --infer and --dry-run
                    result = runner.invoke(main, ["--infer", "--dry-run"])
                    assert result.exit_code == 0

                    # Should have called create_tables
                    mock_db_instance.create_tables.assert_called_once()

                    # Should fetch from beginning (None = 1970-01-01)
                    mock_octopus_instance.consumption.assert_called_once()
                    call_kwargs = mock_octopus_instance.consumption.call_args[1]
                    assert call_kwargs["period_from"] is None

