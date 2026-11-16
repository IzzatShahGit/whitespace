from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import CHAR, DateTime, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from whitespace_api.models.base import Base


class TariffCache(Base):
    """Import duties on one product in one tariff area, as fetched from the source.

    Filled on demand when someone checks duties, and refreshed after
    `tariff_cache_days`: the sources change a few times a year at most. Keyed by tariff
    area rather than market, so the EU's 27 members share one row (reporter "918").
    Holds every partner's rate, so any exporter and its rivals are read from one row.
    """

    __tablename__ = "tariff_cache"

    reporter: Mapped[str] = mapped_column(CHAR(3), primary_key=True)  # WITS-TRAINS code
    hs6: Mapped[str] = mapped_column(CHAR(6), primary_key=True)
    source: Mapped[str] = mapped_column(String(40))
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
