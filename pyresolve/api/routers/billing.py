"""Billing router for the PyResolve API."""

from typing import Optional

import stripe
from fastapi import APIRouter, HTTPException, status

from pyresolve.api.auth import CurrentUser
from pyresolve.api.config import get_settings
from pyresolve.api.database import get_database
from pyresolve.api.models.billing import (
    BillingOverview,
    CheckoutSessionRequest,
    CheckoutSessionResponse,
    PaymentMethodInfo,
    PortalSessionResponse,
    SubscriptionInfo,
    TierInfo,
)

router = APIRouter()

# Tier definitions
TIERS: dict[str, TierInfo] = {
    "free": TierInfo(
        name="free",
        display_name="Free",
        price_monthly=0,
        files_per_month=100,
        llm_calls_per_month=50,
        features=[
            "100 file migrations/month",
            "50 LLM-assisted migrations/month",
            "5 supported libraries",
            "Community support",
        ],
    ),
    "pro": TierInfo(
        name="pro",
        display_name="Pro",
        price_monthly=1900,  # $19.00
        files_per_month=1000,
        llm_calls_per_month=500,
        features=[
            "1,000 file migrations/month",
            "500 LLM-assisted migrations/month",
            "All supported libraries",
            "Priority support",
            "Custom knowledge bases",
        ],
    ),
    "unlimited": TierInfo(
        name="unlimited",
        display_name="Unlimited",
        price_monthly=4900,  # $49.00
        files_per_month=999999999,
        llm_calls_per_month=999999999,
        features=[
            "Unlimited file migrations",
            "Unlimited LLM-assisted migrations",
            "All supported libraries",
            "Priority support",
            "Custom knowledge bases",
            "Usage analytics",
        ],
    ),
    "enterprise": TierInfo(
        name="enterprise",
        display_name="Enterprise",
        price_monthly=0,  # Custom pricing
        files_per_month=999999999,
        llm_calls_per_month=999999999,
        features=[
            "Unlimited migrations",
            "Dedicated support",
            "Custom integrations",
            "SLA guarantees",
            "Self-hosted option",
            "SSO/SAML",
        ],
    ),
}


def get_stripe_client() -> stripe:
    """Get configured Stripe client."""
    settings = get_settings()
    stripe.api_key = settings.stripe_secret_key
    return stripe


@router.get("/tiers", response_model=list[TierInfo])
async def list_tiers() -> list[TierInfo]:
    """List all available pricing tiers."""
    return list(TIERS.values())


@router.get("/tiers/{tier_name}", response_model=TierInfo)
async def get_tier(tier_name: str) -> TierInfo:
    """Get details about a specific tier."""
    tier = TIERS.get(tier_name)
    if not tier:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tier '{tier_name}' not found",
        )
    return tier


@router.get("/subscription", response_model=SubscriptionInfo)
async def get_subscription(user: CurrentUser) -> SubscriptionInfo:
    """Get the current user's subscription information."""
    db = get_database()
    profile = db.get_profile_by_id(user.user_id)

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User profile not found",
        )

    # If user has a Stripe subscription, fetch details
    subscription_id = profile.get("stripe_subscription_id")
    if subscription_id:
        try:
            stripe_client = get_stripe_client()
            subscription = stripe_client.Subscription.retrieve(subscription_id)

            return SubscriptionInfo(
                tier=profile.get("tier", "free"),
                status=subscription.status,
                stripe_subscription_id=subscription_id,
                current_period_start=subscription.current_period_start,
                current_period_end=subscription.current_period_end,
                cancel_at_period_end=subscription.cancel_at_period_end,
            )
        except stripe.error.StripeError:
            pass  # Fall through to basic response

    return SubscriptionInfo(
        tier=profile.get("tier", "free"),
        status="active" if profile.get("tier", "free") != "free" else "free",
    )


@router.get("/overview", response_model=BillingOverview)
async def get_billing_overview(user: CurrentUser) -> BillingOverview:
    """Get complete billing overview for the current user."""
    db = get_database()
    profile = db.get_profile_by_id(user.user_id)

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User profile not found",
        )

    tier = profile.get("tier", "free")
    tier_info = TIERS.get(tier, TIERS["free"])

    subscription = SubscriptionInfo(
        tier=tier,
        status="active" if tier != "free" else "free",
    )

    payment_method: Optional[PaymentMethodInfo] = None

    # Fetch Stripe details if available
    subscription_id = profile.get("stripe_subscription_id")

    if subscription_id:
        try:
            stripe_client = get_stripe_client()
            sub = stripe_client.Subscription.retrieve(subscription_id)

            subscription = SubscriptionInfo(
                tier=tier,
                status=sub.status,
                stripe_subscription_id=subscription_id,
                current_period_start=sub.current_period_start,
                current_period_end=sub.current_period_end,
                cancel_at_period_end=sub.cancel_at_period_end,
            )

            # Get payment method
            if sub.default_payment_method:
                pm = stripe_client.PaymentMethod.retrieve(sub.default_payment_method)
                if pm.type == "card" and pm.card:
                    payment_method = PaymentMethodInfo(
                        id=pm.id,
                        type=pm.type,
                        card_brand=pm.card.brand,
                        card_last4=pm.card.last4,
                        card_exp_month=pm.card.exp_month,
                        card_exp_year=pm.card.exp_year,
                    )
        except stripe.error.StripeError:
            pass

    return BillingOverview(
        subscription=subscription,
        tier_info=tier_info,
        payment_method=payment_method,
    )


@router.post("/checkout", response_model=CheckoutSessionResponse)
async def create_checkout_session(
    request: CheckoutSessionRequest,
    user: CurrentUser,
) -> CheckoutSessionResponse:
    """Create a Stripe checkout session for upgrading subscription."""
    settings = get_settings()
    stripe_client = get_stripe_client()

    # Get or create Stripe customer
    db = get_database()
    profile = db.get_profile_by_id(user.user_id)

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User profile not found",
        )

    customer_id = profile.get("stripe_customer_id")

    if not customer_id:
        # Create Stripe customer
        customer = stripe_client.Customer.create(
            email=profile["email"],
            metadata={
                "user_id": user.user_id,
            },
        )
        customer_id = customer.id

        # Update profile with customer ID
        db.update_profile(user.user_id, {"stripe_customer_id": customer_id})

    # Get the price ID for the requested tier
    if request.tier == "pro":
        price_id = settings.stripe_price_id_pro
    elif request.tier == "unlimited":
        price_id = settings.stripe_price_id_unlimited
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid tier: {request.tier}",
        )

    if not price_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Stripe price not configured",
        )

    # Create checkout session
    success_url = request.success_url or f"{settings.pyresolve_api_url}/billing/success"
    cancel_url = request.cancel_url or f"{settings.pyresolve_api_url}/billing/cancel"

    try:
        session = stripe_client.checkout.Session.create(
            customer=customer_id,
            mode="subscription",
            line_items=[
                {
                    "price": price_id,
                    "quantity": 1,
                }
            ],
            success_url=success_url + "?session_id={CHECKOUT_SESSION_ID}",
            cancel_url=cancel_url,
            metadata={
                "user_id": user.user_id,
                "tier": request.tier,
            },
        )
    except stripe.error.StripeError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create checkout session: {str(e)}",
        ) from e

    return CheckoutSessionResponse(
        checkout_url=session.url,
        session_id=session.id,
    )


@router.get("/portal", response_model=PortalSessionResponse)
async def create_portal_session(user: CurrentUser) -> PortalSessionResponse:
    """Create a Stripe billing portal session for managing subscription."""
    settings = get_settings()
    stripe_client = get_stripe_client()

    db = get_database()
    profile = db.get_profile_by_id(user.user_id)

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User profile not found",
        )

    customer_id = profile.get("stripe_customer_id")

    if not customer_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No billing account found. Please subscribe first.",
        )

    try:
        session = stripe_client.billing_portal.Session.create(
            customer=customer_id,
            return_url=f"{settings.pyresolve_api_url}/billing",
        )
    except stripe.error.StripeError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create portal session: {str(e)}",
        ) from e

    return PortalSessionResponse(portal_url=session.url)


@router.post("/cancel")
async def cancel_subscription(user: CurrentUser) -> dict:
    """Cancel the current subscription at end of billing period."""
    stripe_client = get_stripe_client()

    db = get_database()
    profile = db.get_profile_by_id(user.user_id)

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User profile not found",
        )

    subscription_id = profile.get("stripe_subscription_id")

    if not subscription_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active subscription found",
        )

    try:
        stripe_client.Subscription.modify(
            subscription_id,
            cancel_at_period_end=True,
        )
    except stripe.error.StripeError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to cancel subscription: {str(e)}",
        ) from e

    return {"message": "Subscription will be canceled at end of billing period"}


@router.post("/reactivate")
async def reactivate_subscription(user: CurrentUser) -> dict:
    """Reactivate a subscription that was set to cancel."""
    stripe_client = get_stripe_client()

    db = get_database()
    profile = db.get_profile_by_id(user.user_id)

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User profile not found",
        )

    subscription_id = profile.get("stripe_subscription_id")

    if not subscription_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No subscription found",
        )

    try:
        stripe_client.Subscription.modify(
            subscription_id,
            cancel_at_period_end=False,
        )
    except stripe.error.StripeError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to reactivate subscription: {str(e)}",
        ) from e

    return {"message": "Subscription reactivated"}
