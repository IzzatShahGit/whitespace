from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import CHAR, DateTime, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from whitespace_api.models.base import Base


class MonthlyTradeCache(Base):
    """Monthly imports of one product into one market, as fetched from the source.

    Filled on demand when someone opens the market (EU members via Eurostat, the US
    via the Census Bureau) and refreshed after a few days, since sources publish
    monthly. Holds every supplier, so any exporter's view is computed from one row.
    """

    __tablename__ = "monthly_trade_cache"

    market: Mapped[str] = mapped_column(CHAR(3), primary_key=True)
    hs6: Mapped[str] = mapped_column(CHAR(6), primary_key=True)
    source: Mapped[str] = mapped_column(String(40))
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
