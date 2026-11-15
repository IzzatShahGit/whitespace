"""Trade data tables. Written by the pipeline's load stage, read by the API.

Table names come from the shared contract, so neither side hard-codes them.
"""

from __future__ import annotations

from sqlalchemy import CHAR, Float, Index, Integer, SmallInteger, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from whitespace_api.models.base import Base
from whitespace_shared.gold import COUNTRY_TABLE, MARKET_OPPORTUNITY_TABLE, PRODUCT_TABLE


class Country(Base):
    __tablename__ = COUNTRY_TABLE

    code: Mapped[str] = mapped_column(CHAR(3), primary_key=True)  # ISO alpha-3
    name: Mapped[str] = mapped_column(String(120))


class Product(Base):
    __tablename__ = PRODUCT_TABLE

    hs6: Mapped[str] = mapped_column(CHAR(6), primary_key=True)
    description: Mapped[str] = mapped_column(Text)
    hs_revision: Mapped[str] = mapped_column(String(8))

    __table_args__ = (
        # Fuzzy search on product names ("towels" -> "Towels, terry...").
        Index(
            "ix_ref_product_description_trgm",
            "description",
            postgresql_using="gin",
            postgresql_ops={"description": "gin_trgm_ops"},
        ),
    )


class MarketOpportunity(Base):
    __tablename__ = MARKET_OPPORTUNITY_TABLE

    exporter: Mapped[str] = mapped_column(CHAR(3), primary_key=True)
    hs6: Mapped[str] = mapped_column(CHAR(6), primary_key=True)
    market: Mapped[str] = mapped_column(CHAR(3), primary_key=True)
    data_year: Mapped[int] = mapped_column(SmallInteger)
    market_imports_usd: Mapped[float] = mapped_column(Float)
    import_growth_3y: Mapped[float] = mapped_column(Float)
    top_rival: Mapped[str | None] = mapped_column(CHAR(3))
    top_rival_share_change: Mapped[float | None] = mapped_column(Float)
    exporter_share: Mapped[float] = mapped_column(Float)
    exporter_rca: Mapped[float] = mapped_column(Float)
    score: Mapped[float] = mapped_column(Float)
    rank: Mapped[int] = mapped_column(Integer)
    data_version: Mapped[str] = mapped_column(String(40))

    __table_args__ = (
        # The main query: "ranked markets for this exporter and product".
        Index("ix_gold_mo_exporter_hs6_rank", "exporter", "hs6", "rank"),
    )
