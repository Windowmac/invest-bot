from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field


class SignalDirection(str, Enum):
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"


class TradeSignal(BaseModel):
    ticker: str
    direction: SignalDirection
    confidence: float = Field(ge=0.0, le=1.0)
    source: str  # "research" | "news" | "congress"
    reasoning: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: dict = Field(default_factory=dict)


class NewsItem(BaseModel):
    title: str
    source: str
    url: str
    published_at: datetime
    sentiment_score: float = Field(ge=-1.0, le=1.0)
    tickers_mentioned: list[str] = Field(default_factory=list)


class CongressTrade(BaseModel):
    politician: str
    party: str
    ticker: str
    trade_type: Literal["buy", "sell"]
    amount_range: str
    disclosure_date: datetime
    trade_date: Optional[datetime] = None
    chamber: Optional[str] = None  # "House" or "Senate"
    committee: Optional[str] = None


class AggregatedSignal(BaseModel):
    ticker: str
    direction: SignalDirection
    composite_confidence: float = Field(ge=0.0, le=1.0)
    sources_confirmed: list[str] = Field(default_factory=list)
    research_signal: Optional[TradeSignal] = None
    congress_signal: Optional[TradeSignal] = None
    news_signal: Optional[TradeSignal] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
