from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import CHAR, DateTime
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from whitespace_api.models.base import Base


class TenderCache(Base):
    """Open EU tenders matching one product, shared by every user, refreshed every few
    hours. Kept on failure, so a TED outage shows the last list instead of nothing."""

    __tablename__ = "tender_cache"

    hs6: Mapped[str] = mapped_column(CHAR(6), primary_key=True)
    content: Mapped[dict[str, Any]] = mapped_column(JSONB)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
