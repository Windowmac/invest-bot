"""Unit tests for news aggregator agent."""
from unittest.mock import MagicMock, patch


class TestBuildNewsAgent:
    def test_agent_role(self):
        from agents.news_aggregator import build_news_agent

        agent = build_news_agent()
        assert "News" in agent.role or "Financial" in agent.role

    def test_agent_has_news_tools(self):
        from agents.news_aggregator import build_news_agent

        agent = build_news_agent()
        tool_names = [t.name for t in agent.tools]
        assert "news_search" in tool_names
        assert "market_headlines" in tool_names


class TestRunNewsAnalysis:
    @patch("agents.news_aggregator.Crew")
    def test_returns_string(self, MockCrew):
        from agents.news_aggregator import run_news_analysis

        mock_crew = MagicMock()
        mock_crew.kickoff.return_value = "Market Sentiment Summary: bullish"
        MockCrew.return_value = mock_crew

        result = run_news_analysis()
        assert isinstance(result, str)
        mock_crew.kickoff.assert_called_once()
