"""News Aggregator Agent — NewsAPI + VADER sentiment analysis."""
from __future__ import annotations

import structlog
from crewai import Agent, Crew, Process, Task
from langchain_openai import ChatOpenAI

from schemas.config import settings
from tools.news_tool import MarketHeadlinesTool, NewsSearchTool

log = structlog.get_logger()

_TOPICS = [
    "Federal Reserve interest rates inflation",
    "US economy GDP recession",
    "technology sector earnings",
    "energy commodities oil prices",
]


def _llm() -> ChatOpenAI:
    return ChatOpenAI(model=settings.openai_model, api_key=settings.openai_api_key)


def build_news_agent() -> Agent:
    return Agent(
        role="Financial News & Sentiment Analyst",
        goal=(
            "Monitor financial news and economic headlines to identify market-moving events "
            "and sentiment shifts. Convert news into directional signals for specific stocks or sectors."
        ),
        backstory=(
            "You are a financial journalist turned market analyst with expertise in interpreting "
            "Fed policy, macroeconomic data releases, and corporate events. "
            "You separate signal from noise, focusing only on news with clear market implications."
        ),
        tools=[NewsSearchTool(), MarketHeadlinesTool()],
        llm=_llm(),
        verbose=True,
        allow_delegation=False,
    )


def build_news_task(agent: Agent) -> Task:
    topics_list = "\n".join(f"- {t}" for t in _TOPICS)
    return Task(
        description=(
            "Analyze current financial news to assess market sentiment and identify opportunities:\n\n"
            "1. Fetch overall market headlines with the market_headlines tool\n"
            "2. Search for news on these topics using news_search:\n"
            f"{topics_list}\n"
            "3. Identify stocks mentioned with strong positive or negative catalysts\n"
            "4. Assess overall market sentiment (bullish/bearish/neutral)\n"
            "5. Produce trade signals only for stocks with clear, news-driven catalysts"
        ),
        expected_output=(
            "Market Sentiment Summary: [bullish/bearish/neutral] — [1-sentence rationale]\n\n"
            "Stock-specific signals (if any):\n"
            "SIGNAL: [TICKER] [BUY/SELL/HOLD] [confidence 0.0-1.0]\n"
            "REASONING: [news catalyst and sentiment score driving this signal]\n"
            "---\n"
            "If no high-conviction signals, state: 'No high-conviction news signals today.'"
        ),
        agent=agent,
    )


def run_news_analysis() -> str:
    agent = build_news_agent()
    task = build_news_task(agent)
    crew = Crew(agents=[agent], tasks=[task], process=Process.sequential, verbose=False)
    result = crew.kickoff()
    log.info("news_analysis_complete", preview=str(result)[:200])
    return str(result)
