"""Alpha Vantage tools with automatic yfinance fallback.

Alpha Vantage free tier: 25 requests/day.
A 15-second inter-call delay is enforced to stay within limits.
Any RateLimitError automatically falls back to yfinance.
"""
from __future__ import annotations

import time

import requests
import structlog
import ta
import yfinance as yf
from crewai.tools import BaseTool

from schemas.config import settings

log = structlog.get_logger()

_AV_BASE = "https://www.alphavantage.co/query"
_AV_RATE_LIMIT_SECONDS = 15
_last_av_call: float = 0.0


class _RateLimitError(Exception):
    pass


def _av_get(params: dict) -> dict:
    global _last_av_call
    elapsed = time.time() - _last_av_call
    if elapsed < _AV_RATE_LIMIT_SECONDS:
        time.sleep(_AV_RATE_LIMIT_SECONDS - elapsed)

    params["apikey"] = settings.alpha_vantage_api_key
    resp = requests.get(_AV_BASE, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    _last_av_call = time.time()

    if "Note" in data or "Information" in data:
        msg = data.get("Note") or data.get("Information", "")
        raise _RateLimitError(msg)

    return data


# ── Quote ───────────────────────────────────────────────────────────────────


def _quote_av(ticker: str) -> str:
    data = _av_get({"function": "GLOBAL_QUOTE", "symbol": ticker})
    gq = data.get("Global Quote", {})
    if not gq:
        raise ValueError("Empty response from Alpha Vantage")
    return (
        f"{ticker}: ${gq.get('05. price', 'N/A')} "
        f"({gq.get('10. change percent', 'N/A')} today, "
        f"volume {gq.get('06. volume', 'N/A')})"
    )


def _quote_yf(ticker: str) -> str:
    t = yf.Ticker(ticker)
    hist = t.history(period="5d")
    if hist.empty:
        raise ValueError(f"No yfinance data for {ticker}")
    latest = hist.iloc[-1]
    prev = hist.iloc[-2] if len(hist) > 1 else latest
    change_pct = ((latest["Close"] - prev["Close"]) / prev["Close"]) * 100
    return (
        f"{ticker} [yfinance]: ${latest['Close']:.2f} "
        f"({change_pct:+.2f}% today, volume {int(latest['Volume'])})"
    )


# ── Indicators ──────────────────────────────────────────────────────────────


def _indicators_yf(ticker: str) -> str:
    """Compute RSI, MACD, SMA using ta + yfinance (always used — no AV cost)."""
    hist = yf.Ticker(ticker).history(period="3mo")
    if hist.empty:
        raise ValueError(f"No yfinance data for {ticker}")

    close = hist["Close"]
    rsi = ta.momentum.RSIIndicator(close, window=14).rsi().iloc[-1]
    macd_obj = ta.trend.MACD(close)
    macd = macd_obj.macd().iloc[-1]
    macd_sig = macd_obj.macd_signal().iloc[-1]
    sma20 = ta.trend.SMAIndicator(close, window=20).sma_indicator().iloc[-1]
    sma50 = ta.trend.SMAIndicator(close, window=50).sma_indicator().iloc[-1]
    price = float(close.iloc[-1])

    rsi_label = "oversold" if rsi < 30 else "overbought" if rsi > 70 else "neutral"
    macd_label = "bullish crossover" if macd > macd_sig else "bearish crossover"
    trend = (
        "uptrend (above both SMAs)"
        if price > sma20 and price > sma50
        else "downtrend (below both SMAs)"
        if price < sma20 and price < sma50
        else "mixed trend"
    )

    return (
        f"{ticker} Indicators: RSI={rsi:.1f} ({rsi_label}), "
        f"MACD={macd:.4f} vs Signal={macd_sig:.4f} ({macd_label}), "
        f"SMA20={sma20:.2f}, SMA50={sma50:.2f}, "
        f"Price=${price:.2f} — {trend}"
    )


# ── Fundamentals ─────────────────────────────────────────────────────────────


def _fundamentals_av(ticker: str) -> str:
    data = _av_get({"function": "OVERVIEW", "symbol": ticker})
    return (
        f"{ticker} Fundamentals: "
        f"Sector={data.get('Sector', 'N/A')}, "
        f"MarketCap={data.get('MarketCapitalization', 'N/A')}, "
        f"P/E={data.get('PERatio', 'N/A')}, "
        f"EPS={data.get('EPS', 'N/A')}, "
        f"52wHigh={data.get('52WeekHigh', 'N/A')}, "
        f"52wLow={data.get('52WeekLow', 'N/A')}, "
        f"AnalystTarget={data.get('AnalystTargetPrice', 'N/A')}"
    )


def _fundamentals_yf(ticker: str) -> str:
    info = yf.Ticker(ticker).info
    return (
        f"{ticker} Fundamentals [yfinance]: "
        f"Sector={info.get('sector', 'N/A')}, "
        f"MarketCap={info.get('marketCap', 'N/A')}, "
        f"P/E={info.get('trailingPE', 'N/A')}, "
        f"EPS={info.get('trailingEps', 'N/A')}, "
        f"52wHigh={info.get('fiftyTwoWeekHigh', 'N/A')}, "
        f"52wLow={info.get('fiftyTwoWeekLow', 'N/A')}, "
        f"AnalystTarget={info.get('targetMeanPrice', 'N/A')}"
    )


# ── CrewAI Tool wrappers ─────────────────────────────────────────────────────


class StockQuoteTool(BaseTool):
    name: str = "stock_quote"
    description: str = (
        "Fetch current price and basic quote for a stock ticker. "
        "Input: ticker symbol (e.g. 'AAPL'). "
        "Returns price, volume, and day change percentage."
    )

    def _run(self, ticker: str) -> str:
        ticker = ticker.strip().upper()
        try:
            return _quote_av(ticker)
        except _RateLimitError:
            log.warning("av_rate_limit", ticker=ticker, fallback="yfinance")
            return _quote_yf(ticker)
        except Exception as exc:
            log.error("quote_error", ticker=ticker, error=str(exc))
            return f"Error fetching quote for {ticker}: {exc}"


class TechnicalIndicatorsTool(BaseTool):
    name: str = "technical_indicators"
    description: str = (
        "Compute RSI-14, MACD, SMA-20, and SMA-50 for a stock ticker using yfinance data. "
        "Input: ticker symbol (e.g. 'AAPL'). "
        "Returns indicators and a plain-English trend interpretation."
    )

    def _run(self, ticker: str) -> str:
        ticker = ticker.strip().upper()
        try:
            return _indicators_yf(ticker)
        except Exception as exc:
            log.error("indicators_error", ticker=ticker, error=str(exc))
            return f"Error computing indicators for {ticker}: {exc}"


class FundamentalsTool(BaseTool):
    name: str = "fundamentals"
    description: str = (
        "Fetch fundamental financial data for a stock: P/E, EPS, market cap, "
        "52-week range, sector, and analyst price target. "
        "Input: ticker symbol (e.g. 'AAPL')."
    )

    def _run(self, ticker: str) -> str:
        ticker = ticker.strip().upper()
        try:
            return _fundamentals_av(ticker)
        except _RateLimitError:
            log.warning("av_rate_limit_fundamentals", ticker=ticker, fallback="yfinance")
            return _fundamentals_yf(ticker)
        except Exception as exc:
            log.error("fundamentals_error", ticker=ticker, error=str(exc))
            return f"Error fetching fundamentals for {ticker}: {exc}"
