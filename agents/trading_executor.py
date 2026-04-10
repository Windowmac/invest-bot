"""Trading Executor Agent — places bracket orders on Alpaca after validating signals."""
from __future__ import annotations

import structlog
from crewai import Agent, Crew, Process, Task
from langchain_openai import ChatOpenAI

from schemas.config import settings
from tools.alpaca_tool import GetAccountTool, GetPositionTool, PlaceOrderTool

log = structlog.get_logger()


def _llm() -> ChatOpenAI:
    return ChatOpenAI(model=settings.openai_model, api_key=settings.openai_api_key)


def build_trading_agent() -> Agent:
    return Agent(
        role="Quantitative Trading Executor",
        goal=(
            "Execute trades on Alpaca based on aggregated multi-source signals. "
            "Apply strict risk management: enforce position size limits, daily trade caps, "
            "and require confidence >= 0.65 with confirmation from at least 2 sources."
        ),
        backstory=(
            "You are a disciplined algorithmic trading specialist with a background in "
            "quantitative finance. You prioritize capital preservation above returns. "
            "You require confirmation from multiple independent sources before acting, "
            "and you always check buying power and existing positions before placing orders. "
            "You never override the stop-loss — bracket orders handle that server-side."
        ),
        tools=[GetAccountTool(), PlaceOrderTool(), GetPositionTool()],
        llm=_llm(),
        verbose=True,
        allow_delegation=False,
    )


def build_trading_task(agent: Agent, aggregated_signals: str) -> Task:
    return Task(
        description=(
            f"Review these aggregated signals and execute appropriate trades:\n\n"
            f"{aggregated_signals}\n\n"
            "Trading protocol (follow exactly):\n"
            "1. Call get_account to check buying power, portfolio value, and day-trade count\n"
            "2. For each signal with confidence >= 0.65 AND confirmed by 2+ sources:\n"
            f"   a. Position limit: never exceed ${settings.max_position_size_usd:.0f} per position\n"
            f"   b. Daily trade limit: max {settings.max_daily_trades} trades per day — check daytrade_count\n"
            "   c. Call get_position to check if we already hold the ticker\n"
            "   d. For BUY: only enter if we do NOT already hold it and have sufficient buying power\n"
            "   e. For SELL: only sell if we DO hold a position\n"
            "   f. Call place_order with format 'BUY TICKER QTY' or 'SELL TICKER QTY'\n"
            "      — calculate qty so notional value <= position size limit\n"
            "3. For HOLD signals: no action\n"
            "4. If no signals qualify, clearly explain why (low confidence, insufficient sources, limits reached)"
        ),
        expected_output=(
            "Trading Execution Report:\n"
            "Account: [portfolio value, buying power, day-trade count]\n\n"
            "Trades Executed:\n"
            "  [ticker] [side] [qty] @ market — [rationale]\n"
            "  (or 'None' if no trades placed)\n\n"
            "Trades Skipped:\n"
            "  [ticker] — [reason: low confidence / insufficient sources / limit reached / already held]\n\n"
            "Risk Summary: [brief statement on current exposure]"
        ),
        agent=agent,
    )


def run_trading_execution(aggregated_signals: str) -> str:
    agent = build_trading_agent()
    task = build_trading_task(agent, aggregated_signals)
    crew = Crew(agents=[agent], tasks=[task], process=Process.sequential, verbose=False)
    result = crew.kickoff()
    log.info("trading_execution_complete", preview=str(result)[:200])
    return str(result)
