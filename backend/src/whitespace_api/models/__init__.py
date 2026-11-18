"""Table models. Import every model here so Alembic sees all tables."""

from whitespace_api.models.analytics import AnalyticsDaily, AnalyticsVisitor
from whitespace_api.models.base import Base
from whitespace_api.models.brief import MarketBrief
from whitespace_api.models.chat import ChatMessage, ChatThread
from whitespace_api.models.jobs import EmailSend, EmailVerification, JobLease
from whitespace_api.models.lead import TradeLeads
from whitespace_api.models.pipeline import PipelineContact, PipelineEvent
from whitespace_api.models.profile import UserProfile
from whitespace_api.models.quotes import BusinessDetails, Quote
from whitespace_api.models.recent import MonthlyTradeCache
from whitespace_api.models.requirements import MarketRequirements, RequirementCheck
from whitespace_api.models.shipments import Shipment
from whitespace_api.models.tariff import TariffCache
from whitespace_api.models.tenders import TenderCache
from whitespace_api.models.trade import (
    Country,
    MarketOpportunity,
    MarketSupplier,
    Product,
    SeaRoute,
    SupplierLandscape,
)
from whitespace_api.models.usage import UsageCounter
from whitespace_api.models.user import PasswordReset, RefreshToken, User
from whitespace_api.models.watch import Notification, Watch

__all__ = [
    "AnalyticsDaily",
    "AnalyticsVisitor",
    "Base",
    "BusinessDetails",
    "ChatMessage",
    "ChatThread",
    "Country",
    "EmailSend",
    "EmailVerification",
    "JobLease",
    "MarketBrief",
    "MarketOpportunity",
    "MarketRequirements",
    "MarketSupplier",
    "MonthlyTradeCache",
    "Notification",
    "PasswordReset",
    "PipelineContact",
    "PipelineEvent",
    "Product",
    "Quote",
    "RefreshToken",
    "RequirementCheck",
    "SeaRoute",
    "Shipment",
    "SupplierLandscape",
    "TariffCache",
    "TenderCache",
    "TradeLeads",
    "UsageCounter",
    "User",
    "UserProfile",
    "Watch",
]
