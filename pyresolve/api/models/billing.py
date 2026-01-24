"""Billing models for the PyResolve API."""

from datetime import datetime

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
    stripe_subscription_id: str | None = None
    current_period_start: datetime | None = None
    current_period_end: datetime | None = None
    cancel_at_period_end: bool = False


class CheckoutSessionRequest(BaseModel):
    """Request to create a Stripe checkout session."""

    tier: str = Field(..., pattern="^(pro|unlimited)$")
    success_url: str | None = None
    cancel_url: str | None = None


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
    due_date: datetime | None = None
    hosted_invoice_url: str | None = None
    pdf_url: str | None = None


class PaymentMethodInfo(BaseModel):
    """Payment method information."""

    id: str
    type: str  # card, bank_account, etc.
    card_brand: str | None = None
    card_last4: str | None = None
    card_exp_month: int | None = None
    card_exp_year: int | None = None


class BillingOverview(BaseModel):
    """Complete billing overview for a user."""

    subscription: SubscriptionInfo
    tier_info: TierInfo
    payment_method: PaymentMethodInfo | None = None
    upcoming_invoice: InvoiceInfo | None = None
