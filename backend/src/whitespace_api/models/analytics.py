"""First-party usage counts: no cookies, no addresses, nothing per person.

`AnalyticsDaily` counts events (page views, key actions) per day and page pattern.
`AnalyticsVisitor` holds one salted, day-scoped hash per visitor and day, so unique
visitors can be counted without being recognisable on any other day.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import CHAR, Date, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from whitespace_api.models.base import Base


class AnalyticsDaily(Base):
    __tablename__ = "analytics_daily"

    day: Mapped[date] = mapped_column(Date, primary_key=True)
    event: Mapped[str] = mapped_column(String(40), primary_key=True)
    path: Mapped[str] = mapped_column(String(120), primary_key=True)  # "" when not a page
    count: Mapped[int] = mapped_column(Integer)


class AnalyticsVisitor(Base):
    __tablename__ = "analytics_visitors"

    day: Mapped[date] = mapped_column(Date, primary_key=True)
    visitor: Mapped[str] = mapped_column(CHAR(16), primary_key=True)
