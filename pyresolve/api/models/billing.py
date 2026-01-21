"""Billing models for the PyResolve API."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class TierInfo(BaseModel):
    """Information about a pricing tier."""

    name: str
    display_name: str
    price_monthly: int  # In cents
    files_per_month: int
    llm_calls_per_month: int
    features: list[str]


class SubscriptionInfo(BaseModel):
    """Current subscription information."""

    tier: str
    status: str  # active, canceled, past_due, etc.
    stripe_subscription_id: Optional[str] = None
    current_period_start: Optional[datetime] = None
    current_period_end: Optional[datetime] = None
    cancel_at_period_end: bool = False


class CheckoutSessionRequest(BaseModel):
    """Request to create a Stripe checkout session."""

    tier: str = Field(..., pattern="^(pro|unlimited)$")
    success_url: Optional[str] = None
    cancel_url: Optional[str] = None


class CheckoutSessionResponse(BaseModel):
    """Response with Stripe checkout session."""

    checkout_url: str
    session_id: str


class PortalSessionResponse(BaseModel):
    """Response with Stripe billing portal URL."""

    portal_url: str


class PriceInfo(BaseModel):
    """Stripe price information."""

    id: str
    product_id: str
    unit_amount: int
    currency: str
    recurring_interval: str


class InvoiceInfo(BaseModel):
    """Invoice information."""

    id: str
    status: str
    amount_due: int
    amount_paid: int
    currency: str
    created: datetime
    due_date: Optional[datetime] = None
    hosted_invoice_url: Optional[str] = None
    pdf_url: Optional[str] = None


class PaymentMethodInfo(BaseModel):
    """Payment method information."""

    id: str
    type: str  # card, bank_account, etc.
    card_brand: Optional[str] = None
    card_last4: Optional[str] = None
    card_exp_month: Optional[int] = None
    card_exp_year: Optional[int] = None


class BillingOverview(BaseModel):
    """Complete billing overview for a user."""

    subscription: SubscriptionInfo
    tier_info: TierInfo
    payment_method: Optional[PaymentMethodInfo] = None
    upcoming_invoice: Optional[InvoiceInfo] = None
