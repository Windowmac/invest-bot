"""Unit tests for stock research agent — all external calls are mocked."""
from unittest.mock import MagicMock, patch

import pytest


class TestBuildStockResearchAgent:
    def test_agent_role_and_tools(self):
        from agents.stock_research import build_stock_research_agent

        agent = build_stock_research_agent()
        assert "Analyst" in agent.role or "Research" in agent.role
        tool_names = [t.name for t in agent.tools]
        assert "stock_quote" in tool_names
        assert "technical_indicators" in tool_names
        assert "fundamentals" in tool_names

    def test_task_includes_requested_tickers(self):
        from agents.stock_research import build_research_task, build_stock_research_agent

        agent = build_stock_research_agent()
        task = build_research_task(agent, ["AAPL", "NVDA"])
        assert "AAPL" in task.description
        assert "NVDA" in task.description


class TestRunStockResearch:
    @patch("agents.stock_research.Crew")
    def test_returns_string(self, MockCrew):
        from agents.stock_research import run_stock_research

        mock_crew = MagicMock()
        mock_crew.kickoff.return_value = "SIGNAL: AAPL BUY 0.80\nREASONING: Strong RSI."
        MockCrew.return_value = mock_crew

        result = run_stock_research(["AAPL"])
        assert isinstance(result, str)
        mock_crew.kickoff.assert_called_once()

    @patch("agents.stock_research.Crew")
    def test_handles_no_signals(self, MockCrew):
        from agents.stock_research import run_stock_research

        mock_crew = MagicMock()
        mock_crew.kickoff.return_value = "No high-conviction research signals today."
        MockCrew.return_value = mock_crew

        result = run_stock_research(["XYZ"])
        assert "No high-conviction" in result
