"""Table models. Import every model here so Alembic sees all tables."""

from whitespace_api.models.base import Base
from whitespace_api.models.brief import MarketBrief
from whitespace_api.models.chat import ChatMessage, ChatThread
from whitespace_api.models.profile import UserProfile
from whitespace_api.models.recent import MonthlyTradeCache
from whitespace_api.models.trade import (
    Country,
    MarketOpportunity,
    MarketSupplier,
    Product,
    SupplierLandscape,
)
from whitespace_api.models.usage import UsageCounter
from whitespace_api.models.user import RefreshToken, User

__all__ = [
    "Base",
    "ChatMessage",
    "ChatThread",
    "Country",
    "MarketBrief",
    "MarketOpportunity",
    "MarketSupplier",
    "MonthlyTradeCache",
    "Product",
    "RefreshToken",
    "SupplierLandscape",
    "UsageCounter",
    "User",
    "UserProfile",
]
