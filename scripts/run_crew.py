#!/usr/bin/env python3
"""Entry point: runs the full investment pipeline on a configurable interval.

Usage:
  python scripts/run_crew.py            # Docker / production
  CREW_RUN_INTERVAL_MINUTES=5 python scripts/run_crew.py  # quick local test

The pipeline fires once immediately on startup, then repeats on schedule.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import structlog
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.interval import IntervalTrigger

from agents.crew import run_full_pipeline
from schemas.config import settings

log = structlog.get_logger()


def _pipeline_job() -> None:
    log.info("pipeline_job_start")
    try:
        result = run_full_pipeline()
        log.info("pipeline_job_done", preview=result[:200])
    except Exception as exc:
        log.error("pipeline_job_error", error=str(exc), exc_info=True)


if __name__ == "__main__":
    log.info(
        "invest_bot_starting",
        model=settings.openai_model,
        paper_trading=settings.is_paper_trading,
        interval_minutes=settings.crew_run_interval_minutes,
    )

    # Run once immediately so we don't wait a full interval on startup
    _pipeline_job()

    scheduler = BlockingScheduler()
    scheduler.add_job(
        _pipeline_job,
        trigger=IntervalTrigger(minutes=settings.crew_run_interval_minutes),
        id="investment_pipeline",
        replace_existing=True,
        misfire_grace_time=300,  # allow up to 5 min late before skipping
    )

    log.info("scheduler_started", interval_minutes=settings.crew_run_interval_minutes)
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        log.info("scheduler_stopped")
