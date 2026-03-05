import subprocess
from unittest.mock import MagicMock, patch

import pytest

from scraper import firecrawl_agent


def test_get_api_key_raises_when_keychain_fails():
    with patch(
        "scraper.firecrawl_agent.subprocess.check_output",
        side_effect=subprocess.CalledProcessError(1, ["security"]),
    ):
        with pytest.raises(subprocess.CalledProcessError):
            firecrawl_agent.get_api_key()


def test_run_portal_with_mocked_firecrawl_app():
    app = MagicMock()
    app.agent.return_value = {
        "data": {
            "tender_opportunities": [
                {
                    "tender_title": "Test Tender",
                    "source_url": "https://example.com/tender/1",
                }
            ]
        }
    }

    result = firecrawl_agent.run_portal(
        app=app,
        portal_name="Test Portal",
        portal_url="https://example.com",
        keywords_str="translation, interpretation",
    )

    assert result["status"] == "success"
    assert result["listing_count"] == 1
    assert result["tenders"][0]["tender_title"] == "Test Tender"

    app.agent.assert_called_once()
    assert app.agent.call_args.kwargs["timeout"] == firecrawl_agent.AGENT_TIMEOUT_SECONDS


def test_check_credit_usage_with_mocked_requests_get():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"success": True, "data": {"remaining_credits": 123}}

    with patch("scraper.firecrawl_agent.requests.get", return_value=mock_response) as mock_get:
        result = firecrawl_agent.check_credit_usage("test_api_key")

    assert result == {"success": True, "data": {"remaining_credits": 123}}
    mock_get.assert_called_once_with(
        "https://api.firecrawl.dev/v1/team/credit-usage",
        headers={"Authorization": "Bearer test_api_key"},
    )


def test_pilot_portals_has_exactly_four_entries():
    assert len(firecrawl_agent.PILOT_PORTALS) == 4
