"""Table models. Import every model here so Alembic sees all tables."""

from whitespace_api.models.base import Base
from whitespace_api.models.profile import UserProfile
from whitespace_api.models.recent import MonthlyTradeCache
from whitespace_api.models.trade import Country, MarketOpportunity, MarketSupplier, Product
from whitespace_api.models.user import RefreshToken, User

__all__ = [
    "Base",
    "Country",
    "MarketOpportunity",
    "MarketSupplier",
    "MonthlyTradeCache",
    "Product",
    "RefreshToken",
    "User",
    "UserProfile",
]
