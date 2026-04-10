"""Stock Research Agent — technical and fundamental analysis via Alpha Vantage + yfinance."""
from __future__ import annotations

import structlog
from crewai import Agent, Crew, Process, Task
from langchain_openai import ChatOpenAI

from schemas.config import settings
from tools.alpha_vantage_tool import FundamentalsTool, StockQuoteTool, TechnicalIndicatorsTool

log = structlog.get_logger()

# Default watchlist — edit here or pass tickers at runtime
WATCHLIST: list[str] = [
    "AAPL", "MSFT", "NVDA", "GOOGL", "AMZN",
    "TSLA", "META", "JPM", "SPY", "QQQ",
]


def _llm() -> ChatOpenAI:
    return ChatOpenAI(model=settings.openai_model, api_key=settings.openai_api_key)


def build_stock_research_agent() -> Agent:
    return Agent(
        role="Senior Stock Research Analyst",
        goal=(
            "Analyze stocks using technical indicators (RSI, MACD, SMA) and fundamental data "
            "to produce clear BUY, SELL, or HOLD signals with confidence levels and reasoning."
        ),
        backstory=(
            "You are a seasoned equity analyst with 15 years of experience analyzing US equities. "
            "You combine chart analysis with fundamental valuation. You are rigorous and data-driven "
            "— you never speculate without supporting data, and you always quantify your confidence."
        ),
        tools=[StockQuoteTool(), TechnicalIndicatorsTool(), FundamentalsTool()],
        llm=_llm(),
        verbose=True,
        allow_delegation=False,
    )


def build_research_task(agent: Agent, tickers: list[str] | None = None) -> Task:
    ticker_list = ", ".join(tickers or WATCHLIST)
    return Task(
        description=(
            f"Analyze the following stocks: {ticker_list}\n\n"
            "For each stock:\n"
            "1. Fetch the current quote using the stock_quote tool\n"
            "2. Get technical indicators using the technical_indicators tool\n"
            "3. Get fundamentals using the fundamentals tool\n"
            "4. Synthesize into a BUY/SELL/HOLD signal with confidence (0.0–1.0)\n\n"
            "Focus on the top 3 highest-conviction signals only. "
            "Ignore tickers with conflicting or unclear signals."
        ),
        expected_output=(
            "A list of up to 3 trade signals in this exact format:\n"
            "SIGNAL: [TICKER] [BUY/SELL/HOLD] [confidence 0.0-1.0]\n"
            "REASONING: [2-3 sentences on key technical and fundamental drivers]\n"
            "---\n"
            "Repeat for each signal. If no high-conviction signals exist, state: "
            "'No high-conviction research signals today.'"
        ),
        agent=agent,
    )


def run_stock_research(tickers: list[str] | None = None) -> str:
    agent = build_stock_research_agent()
    task = build_research_task(agent, tickers)
    crew = Crew(agents=[agent], tasks=[task], process=Process.sequential, verbose=False)
    result = crew.kickoff()
    log.info("stock_research_complete", preview=str(result)[:200])
    return str(result)
