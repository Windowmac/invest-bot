"""Alpaca paper trading tools.

All orders use bracket order class so stop-loss and take-profit are handled
server-side by Alpaca — never polled from Python.

Stop-loss percentage and position size limits come from settings/environment.
"""
from __future__ import annotations

import structlog
from crewai.tools import BaseTool

from schemas.config import settings

log = structlog.get_logger()


def _trading_client():
    from alpaca.trading.client import TradingClient

    return TradingClient(
        api_key=settings.alpaca_api_key,
        secret_key=settings.alpaca_secret_key,
        paper=settings.is_paper_trading,
    )


def _data_client():
    from alpaca.data.historical import StockHistoricalDataClient

    return StockHistoricalDataClient(
        api_key=settings.alpaca_api_key,
        secret_key=settings.alpaca_secret_key,
    )


class GetAccountTool(BaseTool):
    name: str = "get_account"
    description: str = (
        "Retrieve Alpaca account status: portfolio value, buying power, cash, "
        "day-trade count, and all open positions. No input required."
    )

    def _run(self, _: str = "") -> str:
        try:
            client = _trading_client()
            account = client.get_account()
            positions = client.get_all_positions()

            pos_lines = []
            for p in positions:
                pos_lines.append(
                    f"  {p.symbol}: {p.qty} shares @ avg ${p.avg_entry_price} "
                    f"(value: ${p.market_value}, P&L: ${p.unrealized_pl})"
                )

            return (
                f"Account ({'PAPER' if settings.is_paper_trading else 'LIVE'}):\n"
                f"  Portfolio Value: ${account.portfolio_value}\n"
                f"  Buying Power:    ${account.buying_power}\n"
                f"  Cash:            ${account.cash}\n"
                f"  Day Trade Count: {account.daytrade_count}\n"
                f"Open Positions ({len(positions)}):\n"
                + ("\n".join(pos_lines) if pos_lines else "  None")
            )
        except Exception as exc:
            log.error("account_error", error=str(exc))
            return f"Error fetching account: {exc}"


class PlaceOrderTool(BaseTool):
    name: str = "place_order"
    description: str = (
        "Place a bracket market order on Alpaca. Stop-loss and take-profit are set automatically. "
        "Input format: 'BUY AAPL 10' or 'SELL MSFT 5' (side, ticker, quantity). "
        "Only call this after confirming buying power and position limits."
    )

    def _run(self, order_str: str) -> str:
        from alpaca.trading.enums import OrderClass, OrderSide, TimeInForce
        from alpaca.trading.requests import MarketOrderRequest

        try:
            parts = order_str.strip().upper().split()
            if len(parts) < 3:
                return "Invalid format. Use: 'BUY AAPL 10' or 'SELL MSFT 5'"

            side_str, ticker, qty_str = parts[0], parts[1], parts[2]

            if side_str not in ("BUY", "SELL"):
                return f"Invalid side '{side_str}'. Must be BUY or SELL."

            side = OrderSide.BUY if side_str == "BUY" else OrderSide.SELL
            qty = float(qty_str)

            # Fetch current price to compute bracket levels
            from alpaca.data.requests import StockLatestQuoteRequest

            data = _data_client()
            quote = data.get_stock_latest_quote(
                StockLatestQuoteRequest(symbol_or_symbols=ticker)
            )
            ask = float(quote[ticker].ask_price or 0)
            bid = float(quote[ticker].bid_price or 0)
            price = ask if ask > 0 else bid

            if price <= 0:
                return f"Could not determine current price for {ticker}."

            stop_price = round(price * (1 - settings.stop_loss_pct), 2)
            take_profit_price = round(price * 1.10, 2)  # fixed 10% take-profit

            order_req = MarketOrderRequest(
                symbol=ticker,
                qty=qty,
                side=side,
                time_in_force=TimeInForce.DAY,
                order_class=OrderClass.BRACKET,
                stop_loss={"stop_price": stop_price},
                take_profit={"limit_price": take_profit_price},
            )

            client = _trading_client()
            order = client.submit_order(order_req)

            log.info(
                "order_placed",
                ticker=ticker,
                side=side_str,
                qty=qty,
                stop=stop_price,
                tp=take_profit_price,
                order_id=str(order.id),
            )

            return (
                f"Order placed: {side_str} {qty} {ticker} @ market. "
                f"Stop-loss: ${stop_price}, Take-profit: ${take_profit_price}. "
                f"Order ID: {order.id}"
            )

        except Exception as exc:
            log.error("order_error", order=order_str, error=str(exc))
            return f"Error placing order '{order_str}': {exc}"


class GetPositionTool(BaseTool):
    name: str = "get_position"
    description: str = (
        "Check the current open position for a specific stock ticker. "
        "Input: ticker symbol (e.g. 'AAPL'). "
        "Returns quantity, average entry price, market value, and unrealized P&L."
    )

    def _run(self, ticker: str) -> str:
        ticker = ticker.strip().upper()
        try:
            client = _trading_client()
            pos = client.get_open_position(ticker)
            return (
                f"{ticker}: {pos.qty} shares @ avg ${pos.avg_entry_price}, "
                f"value ${pos.market_value}, "
                f"P&L ${pos.unrealized_pl} ({pos.unrealized_plpc}%)"
            )
        except Exception as exc:
            if "position does not exist" in str(exc).lower():
                return f"No open position in {ticker}."
            log.error("position_error", ticker=ticker, error=str(exc))
            return f"Error fetching position for {ticker}: {exc}"
