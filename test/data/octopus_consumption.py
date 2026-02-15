"""Test data fixtures for Octopus Energy API responses."""

# URLs for pagination testing
NEXT_PAGE_URL_REAL = (
    "https://api.octopus.energy/v1/electricity-meter-points/mock_mpan_123/meters/"
    "mock_sn_456/consumption/?order_by=period&page=2"
)
NEXT_PAGE_URL_MOCK = (
    "https://api.octopus.energy/v1/electricity-meter-points/mock_e_mpan/meters/"
    "mock_e_sn/consumption/?order_by=period&page=2&page_size=2"
)
PREV_PAGE_URL_MOCK = (
    "https://api.octopus.energy/v1/electricity-meter-points/mock_e_mpan/meters/"
    "mock_e_sn/consumption/?order_by=period&page_size=2"
)

no_args = {
    "count": 13729,
    "next": NEXT_PAGE_URL_REAL,
    "previous": None,
    "results": [
        {
            "consumption": 0.074,
            "interval_start": "2023-01-15T23:30:00Z",
            "interval_end": "2023-01-16T00:00:00Z",
        },
    ],
}

response_one = {
    "count": 2,
    "next": NEXT_PAGE_URL_MOCK,
    "previous": None,
    "results": [
        {
            "consumption": 0.074,
            "interval_start": "2023-01-15T23:30:00Z",
            "interval_end": "2023-01-16T00:00:00Z",
        },
        {
            "consumption": 0.101,
            "interval_start": "2023-01-16T00:00:00Z",
            "interval_end": "2023-01-16T00:30:00Z",
        },
    ],
}

response_two = {
    "count": 2,
    "next": None,
    "previous": PREV_PAGE_URL_MOCK,
    "results": [
        {
            "consumption": 0.06,
            "interval_start": "2023-01-16T00:30:00Z",
            "interval_end": "2023-01-16T01:00:00Z",
        },
        {
            "consumption": 0.017,
            "interval_start": "2023-01-16T01:00:00Z",
            "interval_end": "2023-01-16T01:30:00Z",
        },
    ],
}


