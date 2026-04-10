"""Redis pub/sub helpers and shared state management.

Key namespace: invest_bot:<category>:<detail>
  invest_bot:signals:<ticker>:<source>   — latest signal per ticker/source (24h TTL)
  invest_bot:memory:*                    — CrewAI agent memory (cleared on weekly reset)
  invest_bot:pipeline:*                  — pipeline state/events
"""
from __future__ import annotations

import json
from typing import Any, Callable

import redis
import structlog

from schemas.config import settings

log = structlog.get_logger()

NAMESPACE = "invest_bot"
SIGNAL_TTL_SECONDS = 60 * 60 * 24  # 24 hours


def get_client() -> redis.Redis:
    return redis.Redis(
        host=settings.redis_host,
        port=settings.redis_port,
        db=settings.redis_db,
        password=settings.redis_password or None,
        decode_responses=True,
    )


def _key(suffix: str) -> str:
    return f"{NAMESPACE}:{suffix}"


# ── Publishing ──────────────────────────────────────────────────────────────


def publish(client: redis.Redis, channel: str, payload: dict) -> None:
    """Publish a JSON payload to a namespaced channel."""
    client.publish(_key(channel), json.dumps(payload, default=str))
    log.debug("published", channel=channel, ticker=payload.get("ticker"))


# ── Signal storage ──────────────────────────────────────────────────────────


def store_signal(client: redis.Redis, ticker: str, source: str, signal: dict) -> None:
    """Persist a signal for 24 hours so other agents can read it."""
    key = _key(f"signals:{ticker}:{source}")
    client.set(key, json.dumps(signal, default=str), ex=SIGNAL_TTL_SECONDS)


def get_signals_for_ticker(client: redis.Redis, ticker: str) -> list[dict]:
    """Return all stored signals for a ticker across all sources."""
    pattern = _key(f"signals:{ticker}:*")
    keys = client.keys(pattern)
    signals = []
    for k in keys:
        raw = client.get(k)
        if raw:
            try:
                signals.append(json.loads(raw))
            except json.JSONDecodeError:
                pass
    return signals


# ── Pub/sub subscription ────────────────────────────────────────────────────


def subscribe(
    client: redis.Redis,
    channels: list[str],
    handler: Callable[[str, dict], None],
) -> None:
    """Block and dispatch messages to handler(channel, data).

    channel argument to handler is the un-namespaced name.
    """
    pubsub = client.pubsub()
    pubsub.subscribe(*[_key(c) for c in channels])
    log.info("subscribed", channels=channels)

    for message in pubsub.listen():
        if message["type"] != "message":
            continue
        try:
            data = json.loads(message["data"])
            raw_channel: str = message["channel"]
            short_channel = raw_channel.removeprefix(f"{NAMESPACE}:")
            handler(short_channel, data)
        except Exception as exc:
            log.error("message_handler_error", error=str(exc))


# ── Memory reset helpers ────────────────────────────────────────────────────


def snapshot(client: redis.Redis) -> dict[str, Any]:
    """Dump all invest_bot:* keys to a plain dict for archiving."""
    pattern = _key("*")
    keys = client.keys(pattern)
    data: dict[str, Any] = {}
    for k in keys:
        key_type = client.type(k)
        if key_type == "string":
            data[k] = client.get(k)
        elif key_type == "list":
            data[k] = client.lrange(k, 0, -1)
        elif key_type == "hash":
            data[k] = client.hgetall(k)
        elif key_type == "set":
            data[k] = list(client.smembers(k))
    return data


def flush_memory_keys(client: redis.Redis) -> int:
    """Delete invest_bot:memory:* keys. Returns count deleted."""
    keys = client.keys(_key("memory:*"))
    return client.delete(*keys) if keys else 0


def flush_signal_keys(client: redis.Redis) -> int:
    """Delete invest_bot:signals:* keys. Returns count deleted."""
    keys = client.keys(_key("signals:*"))
    return client.delete(*keys) if keys else 0
