"""NewsAPI tools with VADER sentiment analysis."""
from __future__ import annotations

import re
from datetime import datetime, timedelta

import structlog
from crewai.tools import BaseTool
from newsapi import NewsApiClient
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

from schemas.config import settings

log = structlog.get_logger()

_analyzer = SentimentIntensityAnalyzer()


def _sentiment_label(score: float) -> str:
    if score > 0.05:
        return "positive"
    if score < -0.05:
        return "negative"
    return "neutral"


class NewsSearchTool(BaseTool):
    name: str = "news_search"
    description: str = (
        "Search recent financial news for a company, ticker, or topic. "
        "Input: search query (e.g. 'Apple earnings' or 'Federal Reserve rates'). "
        "Returns top articles with sentiment scores."
    )

    def _run(self, query: str) -> str:
        try:
            client = NewsApiClient(api_key=settings.news_api_key)
            from_date = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d")

            response = client.get_everything(
                q=query,
                language="en",
                sort_by="publishedAt",
                page_size=10,
                from_param=from_date,
            )

            articles = response.get("articles", [])
            if not articles:
                return f"No recent articles found for: {query}"

            lines = []
            for article in articles[:5]:
                title = article.get("title", "")
                source = article.get("source", {}).get("name", "Unknown")
                url = article.get("url", "")
                desc = article.get("description", "") or ""
                compound = _analyzer.polarity_scores(f"{title}. {desc}")["compound"]
                label = _sentiment_label(compound)
                lines.append(
                    f"• [{source}] {title} "
                    f"(sentiment: {label}, score: {compound:+.2f}) — {url}"
                )

            return f"News for '{query}':\n" + "\n".join(lines)

        except Exception as exc:
            log.error("news_search_error", query=query, error=str(exc))
            return f"Error searching news for '{query}': {exc}"


class MarketHeadlinesTool(BaseTool):
    name: str = "market_headlines"
    description: str = (
        "Fetch top business/financial headlines from the past 24 hours and compute "
        "aggregate market sentiment. No input required."
    )

    def _run(self, _: str = "") -> str:
        try:
            client = NewsApiClient(api_key=settings.news_api_key)
            response = client.get_top_headlines(
                category="business",
                language="en",
                page_size=20,
            )

            articles = response.get("articles", [])
            if not articles:
                return "No business headlines available."

            scores = []
            lines = []
            for article in articles:
                title = article.get("title", "")
                if not title:
                    continue
                score = _analyzer.polarity_scores(title)["compound"]
                scores.append(score)
                icon = "+" if score > 0.05 else "-" if score < -0.05 else "~"
                lines.append(f"  [{icon}{score:+.2f}] {title}")

            avg = sum(scores) / len(scores) if scores else 0.0
            overall = "bullish" if avg > 0.05 else "bearish" if avg < -0.05 else "neutral"

            return (
                f"Market Sentiment: {overall} (avg score: {avg:+.2f})\n"
                f"Top Headlines:\n" + "\n".join(lines[:10])
            )

        except Exception as exc:
            log.error("headlines_error", error=str(exc))
            return f"Error fetching headlines: {exc}"
