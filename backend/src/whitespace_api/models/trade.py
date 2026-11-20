"""Trade data tables. Written by the pipeline's load stage, read by the API.

Table names come from the shared contract, so neither side hard-codes them.
"""

from __future__ import annotations

from pgvector.sqlalchemy import Vector
from sqlalchemy import CHAR, Float, Index, Integer, SmallInteger, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from whitespace_api.models.base import Base
from whitespace_shared.gold import (
    COUNTRY_TABLE,
    MARKET_OPPORTUNITY_TABLE,
    MARKET_SUPPLIER_TABLE,
    PRODUCT_TABLE,
    SEA_ROUTE_TABLE,
    SUPPLIER_LANDSCAPE_TABLE,
)

# Word search uses Postgres' English config, which stems words ("sheets" -> "sheet").
# Queries must use this exact expression for the index to apply.
PRODUCT_TSVECTOR_SQL = "to_tsvector('english', description)"


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
        # Word search ("cotton bed sheets" -> "Bed linen: of cotton").
        Index(
            "ix_ref_product_description_fts",
            text(PRODUCT_TSVECTOR_SQL),
            postgresql_using="gin",
        ),
        # Typo-tolerant fallback ("towles" -> "towels").
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
    top_rival_share: Mapped[float | None] = mapped_column(Float)
    market_unit_price_usd_kg: Mapped[float | None] = mapped_column(Float)
    exporter_share: Mapped[float] = mapped_column(Float)
    exporter_rca: Mapped[float] = mapped_column(Float)
    score: Mapped[float] = mapped_column(Float)
    rank: Mapped[int] = mapped_column(Integer)
    data_version: Mapped[str] = mapped_column(String(40))

    __table_args__ = (
        # The main query: "ranked markets for this exporter and product".
        Index("ix_gold_mo_exporter_hs6_rank", "exporter", "hs6", "rank"),
    )


class MarketSupplier(Base):
    __tablename__ = MARKET_SUPPLIER_TABLE

    market: Mapped[str] = mapped_column(CHAR(3), primary_key=True)
    hs6: Mapped[str] = mapped_column(CHAR(6), primary_key=True)
    supplier: Mapped[str] = mapped_column(CHAR(3), primary_key=True)
    value_usd: Mapped[float] = mapped_column(Float)
    share_start: Mapped[float] = mapped_column(Float)
    share_end: Mapped[float] = mapped_column(Float)
    unit_price_usd_kg: Mapped[float | None] = mapped_column(Float)


class SupplierLandscape(Base):
    """The world's largest exporters of each product (for buyers looking for sources)."""

    __tablename__ = SUPPLIER_LANDSCAPE_TABLE

    hs6: Mapped[str] = mapped_column(CHAR(6), primary_key=True)
    supplier: Mapped[str] = mapped_column(CHAR(3), primary_key=True)
    rank: Mapped[int] = mapped_column(Integer)
    exports_usd: Mapped[float] = mapped_column(Float)
    exports_growth_3y: Mapped[float | None] = mapped_column(Float)
    world_share: Mapped[float] = mapped_column(Float)
    markets_served: Mapped[int] = mapped_column(Integer)
    unit_price_usd_kg: Mapped[float | None] = mapped_column(Float)


class SeaRoute(Base):
    """Sea distance between an exporter and a country's main ports (pipeline `routes`).

    One row per (exporter, country); the same distance serves the reverse direction.
    """

    __tablename__ = SEA_ROUTE_TABLE

    origin: Mapped[str] = mapped_column(CHAR(3), primary_key=True)
    dest: Mapped[str] = mapped_column(CHAR(3), primary_key=True)
    sea_nm: Mapped[float] = mapped_column(Float)
    origin_port: Mapped[str] = mapped_column(String(80))
    origin_port_code: Mapped[str] = mapped_column(String(5))
    dest_port: Mapped[str] = mapped_column(String(80))
    dest_port_code: Mapped[str] = mapped_column(String(5))
    origin_inland_km: Mapped[int] = mapped_column(Integer)
    dest_inland_km: Mapped[int] = mapped_column(Integer)


class ProductEmbedding(Base):
    """A product's meaning as a vector (its description plus everyday names), for search
    by description. `text_hash` lets a refresh re-embed only products whose text changed.
    No vector index: an exact scan of ~5,400 rows takes milliseconds and never misses."""

    __tablename__ = "product_embeddings"

    hs6: Mapped[str] = mapped_column(CHAR(6), primary_key=True)
    embedding: Mapped[list[float]] = mapped_column(Vector(768))
    model: Mapped[str] = mapped_column(String(40))
    text_hash: Mapped[str] = mapped_column(String(64))
