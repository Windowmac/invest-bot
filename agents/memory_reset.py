"""Memory reset logic — archives current Redis state then clears agent keys.

Called by scripts/weekly_reset.py (manual or scheduled).
Never flushes the entire Redis DB — only invest_bot:memory:* and invest_bot:signals:* keys.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import structlog

from memory.redis_store import flush_memory_keys, flush_signal_keys, get_client, snapshot

log = structlog.get_logger()

ARCHIVE_DIR = Path("memory/archives")
LOGS_DIR = Path("logs")
LOG_RETENTION_DAYS = 7


def run_memory_reset() -> None:
    log.info("memory_reset_start")
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)

    client = get_client()

    # 1. Snapshot before wiping
    state = snapshot(client)
    stamp = datetime.utcnow().strftime("%Y-%m-%d_%H-%M-%S")
    archive_path = ARCHIVE_DIR / f"{stamp}.json"
    with open(archive_path, "w") as f:
        json.dump(state, f, indent=2, default=str)
    log.info("state_archived", path=str(archive_path), keys=len(state))

    # 2. Clear agent memory keys
    deleted_memory = flush_memory_keys(client)
    log.info("memory_keys_flushed", count=deleted_memory)

    # 3. Clear signal keys
    deleted_signals = flush_signal_keys(client)
    log.info("signal_keys_flushed", count=deleted_signals)

    # 4. Remove log files older than retention window
    _prune_old_logs()

    log.info(
        "memory_reset_complete",
        archive=str(archive_path),
        deleted_memory=deleted_memory,
        deleted_signals=deleted_signals,
    )


def _prune_old_logs() -> None:
    if not LOGS_DIR.exists():
        return
    cutoff = datetime.utcnow().timestamp() - (LOG_RETENTION_DAYS * 86_400)
    removed = 0
    for f in LOGS_DIR.glob("*.log"):
        if f.stat().st_mtime < cutoff:
            f.unlink()
            removed += 1
    if removed:
        log.info("old_logs_pruned", count=removed, retention_days=LOG_RETENTION_DAYS)
