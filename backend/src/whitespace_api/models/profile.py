from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CHAR, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from whitespace_api.models.base import Base


class UserProfile(Base):
    """What a user exports and from where: drives their personalised dashboard.

    Product and country codes deliberately have no foreign keys to the trade tables:
    the pipeline truncates and reloads those, which would fail or cascade into user
    data. The service validates codes against the trade data when a profile is saved.
    """

    __tablename__ = "user_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    exporter: Mapped[str] = mapped_column(CHAR(3))
    role: Mapped[str] = mapped_column(String(20))
    products: Mapped[list[str]] = mapped_column(ARRAY(CHAR(6)))  # ordered, max 5
    current_markets: Mapped[list[str]] = mapped_column(ARRAY(CHAR(3)), server_default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
