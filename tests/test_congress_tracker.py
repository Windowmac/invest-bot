"""Unit tests for congress tracker agent and scraper parsing."""
from datetime import datetime
from unittest.mock import MagicMock, patch

from bs4 import BeautifulSoup


class TestBuildCongressAgent:
    def test_agent_role(self):
        from agents.congress_tracker import build_congress_agent

        agent = build_congress_agent()
        assert any(
            word in agent.role
            for word in ("Congressional", "Congress", "Trading", "Intelligence")
        )

    def test_agent_has_scraper_tool(self):
        from agents.congress_tracker import build_congress_agent

        agent = build_congress_agent()
        tool_names = [t.name for t in agent.tools]
        assert "capitol_trades_scraper" in tool_names


class TestCapitolTradesParser:
    def test_parse_trades_from_fixture(self):
        """Parse the HTML fixture and verify trade extraction."""
        from tools.scraper_tool import _parse_trades

        with open("tests/fixtures/capitol_trades_page.html") as f:
            html = f.read()

        soup = BeautifulSoup(html, "lxml")
        trades = _parse_trades(soup)

        assert len(trades) == 3
        tickers = {t.ticker for t in trades}
        assert "NVDA" in tickers
        assert "MSFT" in tickers
        assert "AAPL" in tickers

        nvda_trade = next(t for t in trades if t.ticker == "NVDA")
        assert nvda_trade.trade_type == "buy"
        assert nvda_trade.politician == "Nancy Pelosi"

    def test_parse_returns_empty_on_blank_html(self):
        from tools.scraper_tool import _parse_trades

        soup = BeautifulSoup("<html><body></body></html>", "lxml")
        trades = _parse_trades(soup)
        assert trades == []


class TestRunCongressTracking:
    @patch("agents.congress_tracker.Crew")
    def test_returns_string(self, MockCrew):
        from agents.congress_tracker import run_congress_tracking

        mock_crew = MagicMock()
        mock_crew.kickoff.return_value = "No high-conviction congressional signals."
        MockCrew.return_value = mock_crew

        result = run_congress_tracking()
        assert isinstance(result, str)
