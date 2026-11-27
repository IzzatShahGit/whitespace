from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from whitespace_api.models.base import Base


class AmazonBestsellers(Base):
    """One weekly capture of Amazon US best-seller lists (top 10 of each category).

    Only the latest two are kept (the older one gives each product's movement), about
    150 small rows of JSON each: well under 100 KB in total.
    """

    __tablename__ = "amazon_bestsellers"

    run_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    items: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
