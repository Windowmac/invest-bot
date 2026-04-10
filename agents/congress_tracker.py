"""Congress Tracking Agent — scrapes Capitol Trades for STOCK Act disclosures."""
from __future__ import annotations

import structlog
from crewai import Agent, Crew, Process, Task
from langchain_openai import ChatOpenAI

from schemas.config import settings
from tools.scraper_tool import CapitolTradesScraper

log = structlog.get_logger()


def _llm() -> ChatOpenAI:
    return ChatOpenAI(model=settings.openai_model, api_key=settings.openai_api_key)


def build_congress_agent() -> Agent:
    return Agent(
        role="Congressional Trading Intelligence Analyst",
        goal=(
            "Monitor US congressional trading disclosures to identify tickers with notable "
            "patterns — multiple members trading the same stock, large position sizes, or "
            "activity from members on relevant committees. Convert strong patterns into signals."
        ),
        backstory=(
            "You are a political finance analyst specializing in STOCK Act disclosures. "
            "You understand that congressional trades are legally required public disclosures "
            "and analyzing them is a legitimate research activity. You focus on pattern analysis "
            "— multiple members, large sizes, committee relevance — not individual trades. "
            "You never imply illegal activity; you analyze publicly available information."
        ),
        tools=[CapitolTradesScraper()],
        llm=_llm(),
        verbose=True,
        allow_delegation=False,
    )


def build_congress_task(agent: Agent) -> Task:
    return Task(
        description=(
            "Scrape and analyze recent congressional trading disclosures:\n\n"
            "1. Use capitol_trades_scraper to fetch recent trades\n"
            "2. Count buys vs. sells per ticker\n"
            "3. Note trades from members of Finance, Banking, Technology, or Defense committees\n"
            "4. Flag unusually large trades (>$50,000 range)\n"
            "5. Only generate a signal if 2+ members trade the same ticker in the same direction, "
            "OR a single member makes a very large trade (>$250,000)\n\n"
            "IMPORTANT: All data here is from public STOCK Act disclosures. "
            "Do not speculate about non-public information."
        ),
        expected_output=(
            "Congressional Trading Summary:\n"
            "- Total trades analyzed: [N]\n"
            "- Tickers with multiple buyers: [list or 'none']\n"
            "- Tickers with multiple sellers: [list or 'none']\n\n"
            "Signals (if any):\n"
            "SIGNAL: [TICKER] [BUY/SELL/HOLD] [confidence 0.0-1.0]\n"
            "REASONING: [members involved, amounts, committee relevance]\n"
            "---\n"
            "If no qualifying patterns, state: 'No high-conviction congressional signals.'"
        ),
        agent=agent,
    )


def run_congress_tracking() -> str:
    agent = build_congress_agent()
    task = build_congress_task(agent)
    crew = Crew(agents=[agent], tasks=[task], process=Process.sequential, verbose=False)
    result = crew.kickoff()
    log.info("congress_tracking_complete", preview=str(result)[:200])
    return str(result)
