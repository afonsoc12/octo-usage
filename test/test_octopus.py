import os
import re
from datetime import UTC, datetime
from unittest import mock

import pytest
import requests
import requests_mock
from requests import Session

from octo_usage.dataclasses import ElectricityConsumption
from octo_usage.octopus import Octopus
from test.data import octopus_consumption as data


class TestOctopus:
    @pytest.fixture
    def mock_adapter(self):
        return requests_mock.Adapter()

    @pytest.fixture
    def instance(self, mock_adapter):
        mock_env_vars = {
            "OCTOPUS_API_KEY": "mock_api_key",
            "OCTOPUS_ELECTRICITY_MPAN": "mock_e_mpan",
            "OCTOPUS_ELECTRICITY_SN": "mock_e_sn",
        }
        with mock.patch.dict(os.environ, mock_env_vars):
            o = Octopus()
            o.mount("https://", mock_adapter)
            return o

    def test_consumption_no_args(self, instance):
        expected_kwargs = {
            "period_from": "1970-01-01T00:00:00Z",
            "period_to": None,
            "page_size": 1000,
            "order_by": "period",
            "group_by": None,
        }
        resp = {
            "count": 123,
            "next": None,
            "results": [
                {
                    "consumption": 0.074,
                    "interval_start": "2023-01-15T23:30:00Z",
                    "interval_end": "2023-01-16T00:00:00Z",
                },
            ],
        }
        with mock.patch.object(Session, "request") as mock_request:
            mock_response = mock.Mock()
            mock_response.json.return_value = resp
            mock_request.return_value = mock_response
            _ = instance.consumption()
            assert mock_request.call_count == 1
            call_kwargs = mock_request.call_args[1]
            assert call_kwargs.get("params", {}).get("period_from") == expected_kwargs["period_from"]

    def test_consumption_recursive(self, instance, mock_adapter):
        with mock.patch.object(instance, "hooks", {}):
            mock_adapter.register_uri(
                "GET",
                re.compile(r"/.*\/consumption/?(\?.*)?$"),
                [{"json": data.response_one}, {"json": data.response_two}],
            )

            cons = instance.consumption()

            assert mock_adapter.call_count == 2
            assert "page=" not in mock_adapter.request_history[0].query
            assert "page=2" in mock_adapter.request_history[1].query
            assert cons == [
                ElectricityConsumption.from_dict(
                    {
                        "mpan": instance.electricity_mpan,
                        "meter_sn": instance.electricity_sn,
                        **cons_data,
                    }
                )
                for cons_data in data.response_one["results"] + data.response_two["results"]
            ]

    def test_consumption_with_url(self, instance, mock_adapter):
        mock_adapter.register_uri("GET", url=re.compile(r"/.*\/consumption/?(\?.*)?$"), json=data.response_two)

        path = "https://test.com/api/path/consumption"
        with (
            mock.patch.object(instance, "hooks", {}),
            mock.patch.object(Session, "request", wraps=instance.request) as wrap_request,
        ):
            cons = instance.consumption(url=path)

            wrap_request.assert_called_once()
            assert cons == [
                ElectricityConsumption.from_dict(
                    {
                        "mpan": instance.electricity_mpan,
                        "meter_sn": instance.electricity_sn,
                        **cons_data,
                    }
                )
                for cons_data in data.response_two["results"]
            ]

    def test_session_properties(self, instance):
        assert isinstance(instance, Session)
        assert instance.auth.username == instance.api_key
        assert instance.auth.password == ""

    def test_session_hooks(self, instance):
        headers = requests.structures.CaseInsensitiveDict()
        now = datetime.now(UTC)
        headers["date"] = now.strftime("%a, %d %b %Y %H:%M:%S %Z")

        mock_adapter = requests_mock.Adapter()
        mock_adapter.register_uri("GET", "mock://test.com", headers=headers)
        instance.mount("mock://", mock_adapter)

        resp = instance.get("mock://test.com")
        assert resp.request_timestamp == now.replace(microsecond=0)

    def test_get_endpoint_slash(self, instance):
        with mock.patch("requests.Session.request") as mock_request:
            mock_response = mock.Mock()
            mock_response.raise_for_status.return_value = None
            mock_request.return_value = mock_response

            instance._request("GET", "endpoint-a")
            instance._request("GET", "endpoint-a")
            assert mock_request.call_count == 2
            # Both calls should have the same URL
            call1_url = mock_request.call_args_list[0][0][1]
            call2_url = mock_request.call_args_list[1][0][1]
            assert call1_url == call2_url == "https://api.octopus.energy/v1/endpoint-a"
            assert mock_request.call_count == 2
            # Both calls should have the same URL
            call1_url = mock_request.call_args_list[0][0][1]
            call2_url = mock_request.call_args_list[1][0][1]
            assert call1_url == call2_url == "https://api.octopus.energy/v1/endpoint-a"

    def test_get_exc_no_url_and_endpoint(self, instance):
        # _request now requires an endpoint parameter
        with pytest.raises(TypeError):
            instance._request("GET")
