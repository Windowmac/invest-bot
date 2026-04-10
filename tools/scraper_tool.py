"""Capitol Trades scraper using Playwright + BeautifulSoup.

IMPORTANT NOTES:
- Capitol Trades has no public API; scraping is the only option.
- The site disallows crawlers in robots.txt — use responsibly and infrequently.
- Cloudflare bot protection may block headless browsers; if so, scraping will fail
  gracefully and return an error message rather than crashing the pipeline.
- HTML selectors here are based on the Capitol Trades page structure as observed
  in 2024. They WILL break if the site redesigns — review _parse_trades() if results
  are empty and no obvious error is returned.
- Consider switching to Quiver Quant API (~$20/mo) for a more reliable data source.
"""
from __future__ import annotations

import time
from datetime import datetime
from typing import Optional

import structlog
from bs4 import BeautifulSoup
from crewai.tools import BaseTool

from schemas.config import settings
from schemas.signals import CongressTrade

log = structlog.get_logger()


def _parse_date(raw: str) -> Optional[datetime]:
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%b %d, %Y", "%B %d, %Y"):
        try:
            return datetime.strptime(raw.strip(), fmt)
        except ValueError:
            continue
    return None


class CapitolTradesScraper(BaseTool):
    name: str = "capitol_trades_scraper"
    description: str = (
        "Scrape recent US congressional trading disclosures from Capitol Trades. "
        "Returns publicly disclosed buy/sell trades by members of Congress (STOCK Act data). "
        "No input required."
    )

    def _run(self, _: str = "") -> str:
        try:
            from playwright.sync_api import sync_playwright

            log.info("scraping_capitol_trades", url=settings.capitol_trades_url)

            with sync_playwright() as pw:
                browser = pw.chromium.launch(headless=settings.playwright_headless)
                ctx = browser.new_context(
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/124.0.0.0 Safari/537.36"
                    )
                )
                page = ctx.new_page()
                page.goto(
                    settings.capitol_trades_url,
                    wait_until="networkidle",
                    timeout=30_000,
                )
                time.sleep(settings.scrape_delay_seconds)
                html = page.content()
                browser.close()

            soup = BeautifulSoup(html, "lxml")
            trades = _parse_trades(soup)

            if not trades:
                return (
                    "No trades parsed from Capitol Trades. "
                    "The site structure may have changed or Cloudflare is blocking access. "
                    "Check _parse_trades() selectors in tools/scraper_tool.py."
                )

            lines = []
            for t in trades[:20]:
                date_str = t.disclosure_date.strftime("%Y-%m-%d")
                lines.append(
                    f"• {t.politician} ({t.party}) — "
                    f"{t.trade_type.upper()} ${t.ticker} {t.amount_range} "
                    f"(disclosed: {date_str})"
                )

            return (
                f"Recent Congressional Trades ({len(trades)} found):\n"
                + "\n".join(lines)
            )

        except Exception as exc:
            log.error("scraper_error", error=str(exc))
            return (
                f"Error scraping Capitol Trades: {exc}. "
                "Scraping may be blocked or the page structure changed."
            )


def _parse_trades(soup: BeautifulSoup) -> list[CongressTrade]:
    """Parse CongressTrade objects from the Capitol Trades HTML.

    Selectors target the table layout observed in 2024. If the site redesigns,
    update the selectors here. Log warnings for individual row failures rather
    than raising so the agent degrades gracefully.
    """
    trades: list[CongressTrade] = []

    rows = soup.select("table tbody tr")
    if not rows:
        # Fallback: some page states render card/article layout
        rows = soup.select("article, [data-trade-id]")

    for row in rows:
        try:
            cells = row.find_all("td")
            if len(cells) < 5:
                continue

            politician = cells[0].get_text(strip=True)

            # Ticker may be in a dedicated element or a cell
            ticker_el = row.select_one("[data-ticker], .ticker, .stock-ticker")
            ticker = (
                ticker_el.get_text(strip=True)
                if ticker_el
                else cells[2].get_text(strip=True)
            )
            ticker = ticker.upper().strip()

            trade_text = cells[3].get_text(strip=True).lower()
            trade_type = (
                "buy" if ("buy" in trade_text or "purchase" in trade_text) else "sell"
            )

            amount = cells[4].get_text(strip=True)

            date_el = row.select_one("time, .disclosure-date, [datetime]")
            raw_date = (
                (date_el.get("datetime") or date_el.get_text(strip=True))
                if date_el
                else ""
            )
            disclosure_date = _parse_date(raw_date) or datetime.utcnow()

            party_el = row.select_one(".party, [data-party]")
            party = party_el.get_text(strip=True) if party_el else "Unknown"

            if ticker and politician:
                trades.append(
                    CongressTrade(
                        politician=politician,
                        party=party,
                        ticker=ticker,
                        trade_type=trade_type,
                        amount_range=amount,
                        disclosure_date=disclosure_date,
                    )
                )
        except Exception as exc:
            log.warning("row_parse_error", error=str(exc))
            continue

    return trades
