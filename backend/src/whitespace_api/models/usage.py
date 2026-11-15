from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from whitespace_api.models.base import Base


class UsageCounter(Base):
    """How many metered actions (chat messages, …) a user has used on a day.

    Incremented with one conditional upsert, so concurrent requests can't overshoot
    the limit.
    """

    __tablename__ = "usage_counters"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    kind: Mapped[str] = mapped_column(String(20), primary_key=True)
    day: Mapped[date] = mapped_column(Date, primary_key=True)
    count: Mapped[int] = mapped_column(Integer)
