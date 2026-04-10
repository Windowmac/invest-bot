"""Main CrewAI orchestration — runs the full investment pipeline.

Pipeline order (sequential):
  1. Stock Research Agent  — technical + fundamental signals
  2. News Aggregator Agent — news sentiment signals
  3. Congress Tracker Agent — STOCK Act disclosure signals
  4. Signal Aggregator     — combines outputs, requires multi-source confirmation
  5. Trading Executor      — places bracket orders on qualifying signals
"""
from __future__ import annotations

import structlog
from crewai import Agent, Crew, Process, Task
from langchain_openai import ChatOpenAI

from agents.congress_tracker import build_congress_agent, build_congress_task
from agents.news_aggregator import build_news_agent, build_news_task
from agents.stock_research import build_research_task, build_stock_research_agent
from agents.trading_executor import build_trading_agent, build_trading_task
from memory.redis_store import get_client, publish
from schemas.config import settings

log = structlog.get_logger()


def _llm() -> ChatOpenAI:
    return ChatOpenAI(model=settings.openai_model, api_key=settings.openai_api_key)


def _build_aggregator_agent() -> Agent:
    return Agent(
        role="Chief Investment Signal Aggregator",
        goal=(
            "Synthesize outputs from the stock research, news, and congressional trading agents "
            "into a unified ranked list of trade recommendations. Filter for multi-source "
            "confirmation and assign composite confidence scores."
        ),
        backstory=(
            "You are a chief investment officer who receives independent analysis from three teams "
            "and must decide which ideas merit capital. You are conservative: you require at least "
            "two sources pointing the same direction before considering an idea actionable. "
            "You rank ideas by composite confidence and discard weak or conflicting signals."
        ),
        tools=[],
        llm=_llm(),
        verbose=True,
        allow_delegation=False,
    )


def _build_aggregation_task(
    aggregator: Agent,
    research_task: Task,
    news_task: Task,
    congress_task: Task,
) -> Task:
    return Task(
        description=(
            "Review the outputs from the Stock Research, News, and Congressional Trading agents "
            "(available as context from previous tasks). Produce a unified signal list.\n\n"
            "Scoring rules:\n"
            "- 3 sources agree on same direction: composite_confidence = max(individual) + 0.15, cap at 1.0\n"
            "- 2 sources agree: composite_confidence = average of the two\n"
            "- Only 1 source: discard unless individual confidence >= 0.85\n"
            "- Conflicting directions (one BUY, one SELL): discard\n\n"
            "Output every qualifying signal for the Trading Executor."
        ),
        expected_output=(
            "AGGREGATED SIGNALS FOR TRADING EXECUTOR:\n\n"
            "SIGNAL: [TICKER] [BUY/SELL/HOLD] [composite_confidence]\n"
            "SOURCES: [research / news / congress — list which confirmed]\n"
            "REASONING: [combined rationale from confirming sources]\n"
            "---\n"
            "Repeat for each qualifying signal.\n"
            "If none qualify, state: 'NO QUALIFYING SIGNALS — [brief reason]'"
        ),
        agent=aggregator,
        context=[research_task, news_task, congress_task],
    )


def build_full_crew() -> Crew:
    research_agent = build_stock_research_agent()
    news_agent = build_news_agent()
    congress_agent = build_congress_agent()
    aggregator = _build_aggregator_agent()
    trading_agent = build_trading_agent()

    research_task = build_research_task(research_agent)
    news_task = build_news_task(news_agent)
    congress_task = build_congress_task(congress_agent)
    aggregation_task = _build_aggregation_task(
        aggregator, research_task, news_task, congress_task
    )
    # Trading task description references aggregation_task output via context
    trading_task = Task(
        description=(
            "Execute trades based on the AGGREGATED SIGNALS provided by the Signal Aggregator "
            "(available in the prior task context). Follow the standard trading protocol:\n"
            "1. Check account status with get_account\n"
            "2. For each signal with composite_confidence >= 0.65: evaluate for execution\n"
            "3. Respect all position size and daily trade limits\n"
            "4. Place bracket orders via place_order for qualifying signals"
        ),
        expected_output=(
            "Trading Execution Report:\n"
            "Account: [portfolio value, buying power]\n"
            "Trades Executed: [list or 'None']\n"
            "Trades Skipped: [list with reasons]\n"
            "Risk Summary: [current exposure statement]"
        ),
        agent=trading_agent,
        context=[aggregation_task],
    )

    return Crew(
        agents=[research_agent, news_agent, congress_agent, aggregator, trading_agent],
        tasks=[research_task, news_task, congress_task, aggregation_task, trading_task],
        process=Process.sequential,
        verbose=True,
    )


def run_full_pipeline() -> str:
    log.info("pipeline_start")
    crew = build_full_crew()
    result = crew.kickoff()
    result_str = str(result)
    log.info("pipeline_complete", preview=result_str[:300])

    try:
        redis_client = get_client()
        publish(redis_client, "pipeline_complete", {"status": "complete", "preview": result_str[:500]})
    except Exception as exc:
        log.warning("redis_publish_failed", error=str(exc))

    return result_str
