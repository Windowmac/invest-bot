"""Unit tests for trading executor agent."""
from unittest.mock import MagicMock, patch


class TestBuildTradingAgent:
    def test_agent_role(self):
        from agents.trading_executor import build_trading_agent

        agent = build_trading_agent()
        assert "Trading" in agent.role or "Executor" in agent.role

    def test_agent_requires_multi_source_confirmation(self):
        """Backstory should mention requiring multiple sources — key risk control."""
        from agents.trading_executor import build_trading_agent

        agent = build_trading_agent()
        backstory_lower = agent.backstory.lower()
        assert any(
            phrase in backstory_lower
            for phrase in ("multiple", "confirmation", "two", "independent")
        )

    def test_agent_has_alpaca_tools(self):
        from agents.trading_executor import build_trading_agent

        agent = build_trading_agent()
        tool_names = [t.name for t in agent.tools]
        assert "get_account" in tool_names
        assert "place_order" in tool_names
        assert "get_position" in tool_names


class TestRunTradingExecution:
    @patch("agents.trading_executor.Crew")
    def test_no_signals_takes_no_action(self, MockCrew):
        from agents.trading_executor import run_trading_execution

        mock_crew = MagicMock()
        mock_crew.kickoff.return_value = "NO QUALIFYING SIGNALS — all below confidence threshold."
        MockCrew.return_value = mock_crew

        result = run_trading_execution("NO QUALIFYING SIGNALS")
        assert isinstance(result, str)
        mock_crew.kickoff.assert_called_once()

    @patch("agents.trading_executor.Crew")
    def test_returns_execution_report(self, MockCrew):
        from agents.trading_executor import run_trading_execution

        signals = "SIGNAL: AAPL BUY 0.80\nSOURCES: research, news\nREASONING: Strong momentum."
        mock_crew = MagicMock()
        mock_crew.kickoff.return_value = (
            "Trading Execution Report:\n"
            "Account: $50,000 portfolio, $20,000 buying power\n"
            "Trades Executed: AAPL BUY 5 @ market\n"
            "Trades Skipped: None\n"
            "Risk Summary: $1,000 exposure in AAPL (2% of portfolio)"
        )
        MockCrew.return_value = mock_crew

        result = run_trading_execution(signals)
        assert "Trading Execution Report" in result
