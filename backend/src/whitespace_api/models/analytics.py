"""First-party usage analytics, no cookies and no stored addresses.

`AnalyticsDaily` counts events (page views, key actions) per day and page pattern.
`AnalyticsVisitor` holds one salted, day-scoped hash per visitor and day, so unique
visitors can be counted without being recognisable on any other day.
`Visit` is one visit to the site (pages seen within 30 minutes of each other): where it
came from, the country (looked up from the address, which is then dropped), the device,
pages and time spent. Visits by signed-in people are linked to their account.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import CHAR, BigInteger, Date, DateTime, ForeignKey, Index, Integer, String
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


class Visit(Base):
    __tablename__ = "visits"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    visitor: Mapped[str] = mapped_column(CHAR(16))  # same day-scoped hash as above
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    country: Mapped[str | None] = mapped_column(CHAR(2))  # ISO 3166-1 alpha-2
    source: Mapped[str] = mapped_column(String(60))  # "Google", "LinkedIn", "Direct", a host
    referrer: Mapped[str | None] = mapped_column(String(120))  # host only
    utm_campaign: Mapped[str | None] = mapped_column(String(60))
    landing: Mapped[str] = mapped_column(String(120))
    device: Mapped[str] = mapped_column(String(10))  # desktop | mobile | tablet
    browser: Mapped[str] = mapped_column(String(20))
    os: Mapped[str] = mapped_column(String(20))
    pages: Mapped[int] = mapped_column(Integer, default=1)
    engaged_seconds: Mapped[int] = mapped_column(Integer, default=0)

    __table_args__ = (
        Index("ix_visits_visitor_last_seen", "visitor", "last_seen_at"),
        Index("ix_visits_started", "started_at"),
        Index("ix_visits_user_started", "user_id", "started_at"),
    )


class VisitPage(Base):
    """One page in a visit, in order, with the time spent on it."""

    __tablename__ = "visit_pages"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    visit_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("visits.id", ondelete="CASCADE"))
    path: Mapped[str] = mapped_column(String(120))
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    seconds: Mapped[int] = mapped_column(Integer, default=0)

    __table_args__ = (Index("ix_visit_pages_visit_at", "visit_id", "at"),)
