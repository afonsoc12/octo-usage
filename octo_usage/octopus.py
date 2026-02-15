import os
from datetime import UTC, datetime
from http.client import responses
from urllib.parse import urljoin

import requests
from requests import Session
from requests.auth import HTTPBasicAuth
from requests.exceptions import HTTPError

from octo_usage.dataclasses import ElectricityConsumption

from .logging_config import get_logger

logger = get_logger(__name__)


class Octopus(Session):
    """Octopus Energy API client inheriting from requests.Session.

    Handles authentication, request logging, and pagination.
    """

    BASE_URL = "https://api.octopus.energy/"
    API_ENDPOINT = "v1/"
    DEFAULT_PERIOD_FROM = "1970-01-01T00:00:00Z"

    def __init__(self, page_size=1000):
        super().__init__()
        self.api_key = os.getenv("OCTOPUS_API_KEY")
        self.electricity_mpan = os.getenv("OCTOPUS_ELECTRICITY_MPAN")
        self.electricity_sn = os.getenv("OCTOPUS_ELECTRICITY_SN")
        self.page_size = page_size

        # Set up authentication
        self.auth = HTTPBasicAuth(self.api_key, "")

        # Add request timestamp hook
        self.hooks["response"].append(self._request_timestamp)

    def __repr__(self):
        return f"{self.__class__.__name__}(mpan='{self.electricity_mpan}', sn='{self.electricity_sn}')"

    def _request_timestamp(self, r, *args, **kwargs):
        """Hook to capture request timestamp from response headers."""
        try:
            r.request_timestamp = datetime.strptime(r.headers.get("Date"), "%a, %d %b %Y %H:%M:%S %Z").replace(
                tzinfo=UTC
            )
        except ValueError, TypeError:
            r.request_timestamp = datetime.now(UTC)
        return r

    def _request(self, method, endpoint, **kwargs):
        """Make a request to the Octopus API with error handling and logging.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint path (relative)
            **kwargs: Keyword arguments for session.request (e.g., params, data)

        Returns:
            requests.Response object

        Raises:
            HTTPError: If the response status indicates an error
        """
        # Log the request parameters at debug level
        logger.debug(f"Octopus API request: {method} {endpoint}  params: {kwargs.get('params', {})}")

        # Build full URL
        url = urljoin(urljoin(self.BASE_URL, self.API_ENDPOINT), endpoint)

        # Make the request using parent class
        req = super().request(method, url, **kwargs)

        try:
            req.raise_for_status()
        except HTTPError:
            logger.error(f"Octopus API error {req.status_code} {responses.get(req.status_code, 'Unknown')}")
            if req.headers.get("Content-Type") == "application/json":
                try:
                    error_data = req.json()
                    logger.error(f"Error response: {error_data}")
                except Exception:
                    pass
            raise

        return req

    def consumption(self, url=None, period_from=None, period_to=None, on_page=None):
        """Fetch electricity consumption data.

        Args:
            url: Full URL for pagination (overrides endpoint/params)
            period_from: Start datetime (ISO 8601, defaults to 1970-01-01)
            period_to: End datetime (ISO 8601)
            on_page: Optional callback(page_data) called for each page before recursion

        Returns:
            List of ElectricityConsumption dataclass instances
        """
        if url:
            # URL override, in case it's a paginated request
            # Log pagination request
            logger.debug(f"Octopus API request: GET {url}")
            req = self.request("GET", url)
        else:
            # Default period_from to UNIX epoch if not provided
            if not period_from:
                period_from = self.DEFAULT_PERIOD_FROM
                logger.info(f"No period_from provided, defaulting to {period_from}")

            endpoint = f"electricity-meter-points/{self.electricity_mpan}/meters/{self.electricity_sn}/consumption"
            parameters = {
                "period_from": period_from,
                "period_to": period_to,
                "page_size": self.page_size,
                "order_by": "period",
                "group_by": None,
            }

            logger.debug(f"Fetching consumption from {period_from} to {period_to or 'now'}")

            req = self._request("GET", endpoint, params=parameters)

        try:
            data = req.json()

            # Log debug info only if results are present
            if data["results"]:
                logger.debug(
                    f"Got {data['count']} data points from "
                    f"{data['results'][0]['interval_start']} to "
                    f"{data['results'][-1]['interval_end']}"
                )
            else:
                logger.debug(f"API response contains {data['count']} total records but no results in this page")

            consumption = [
                ElectricityConsumption.from_dict(
                    {
                        "mpan": self.electricity_mpan,
                        "meter_sn": self.electricity_sn,
                        **cons,
                    }
                )
                for cons in data["results"]
            ]

            # Call callback if provided (for per-page processing)
            if on_page and consumption:
                on_page(consumption)

            # Handle pagination
            if data.get("next"):
                logger.debug("Fetching next page of consumption data")
                consumption += self.consumption(url=data.get("next"), on_page=on_page)

            return consumption

        except requests.exceptions.HTTPError:
            raise
