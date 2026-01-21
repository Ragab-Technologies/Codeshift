"""Webhooks router for the PyResolve API."""

import stripe
from fastapi import APIRouter, Header, HTTPException, Request, status

from pyresolve.api.config import get_settings
from pyresolve.api.database import get_database

router = APIRouter()


def get_stripe_client() -> stripe:
    """Get configured Stripe client."""
    settings = get_settings()
    stripe.api_key = settings.stripe_secret_key
    return stripe


@router.post("/stripe")
async def handle_stripe_webhook(
    request: Request,
    stripe_signature: str = Header(None, alias="Stripe-Signature"),
) -> dict:
    """Handle Stripe webhook events.

    Handles the following events:
    - checkout.session.completed: User completed checkout, activate subscription
    - customer.subscription.created: New subscription created
    - customer.subscription.updated: Subscription updated (upgrade/downgrade)
    - customer.subscription.deleted: Subscription canceled
    - invoice.paid: Invoice paid successfully
    - invoice.payment_failed: Payment failed
    """
    settings = get_settings()
    stripe_client = get_stripe_client()

    # Get raw body for signature verification
    payload = await request.body()

    if not stripe_signature:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing Stripe-Signature header",
        )

    try:
        event = stripe_client.Webhook.construct_event(
            payload,
            stripe_signature,
            settings.stripe_webhook_secret,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid payload",
        ) from e
    except stripe.error.SignatureVerificationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid signature",
        ) from e

    # Handle the event
    event_type = event["type"]
    data = event["data"]["object"]

    try:
        if event_type == "checkout.session.completed":
            await handle_checkout_completed(data)
        elif event_type == "customer.subscription.created":
            await handle_subscription_created(data)
        elif event_type == "customer.subscription.updated":
            await handle_subscription_updated(data)
        elif event_type == "customer.subscription.deleted":
            await handle_subscription_deleted(data)
        elif event_type == "invoice.paid":
            await handle_invoice_paid(data)
        elif event_type == "invoice.payment_failed":
            await handle_invoice_payment_failed(data)
        else:
            # Log unhandled events for debugging
            print(f"Unhandled webhook event: {event_type}")
    except Exception as e:
        # Log error but don't fail the webhook
        print(f"Error handling webhook {event_type}: {e}")
        # Still return 200 to prevent Stripe retries for non-critical errors

    return {"received": True}


async def handle_checkout_completed(session: dict) -> None:
    """Handle successful checkout session completion."""
    db = get_database()

    # Get user ID from metadata
    user_id = session.get("metadata", {}).get("user_id")
    tier = session.get("metadata", {}).get("tier", "pro")

    if not user_id:
        print("Checkout session missing user_id in metadata")
        return

    # Get subscription ID
    subscription_id = session.get("subscription")
    customer_id = session.get("customer")

    # Update user's profile
    db.update_profile(
        user_id,
        {
            "tier": tier,
            "stripe_customer_id": customer_id,
            "stripe_subscription_id": subscription_id,
        },
    )

    print(f"User {user_id} upgraded to {tier}")


async def handle_subscription_created(subscription: dict) -> None:
    """Handle new subscription creation."""
    db = get_database()

    customer_id = subscription.get("customer")
    subscription_id = subscription.get("id")

    # Find user by customer ID
    result = (
        db.client.table("profiles").select("id").eq("stripe_customer_id", customer_id).execute()
    )

    if not result.data:
        print(f"No user found for customer {customer_id}")
        return

    user_id = result.data[0]["id"]

    # Determine tier from price
    items = subscription.get("items", {}).get("data", [])
    if items:
        price_id = items[0].get("price", {}).get("id")
        settings = get_settings()

        if price_id == settings.stripe_price_id_pro:
            tier = "pro"
        elif price_id == settings.stripe_price_id_unlimited:
            tier = "unlimited"
        else:
            tier = "pro"  # Default
    else:
        tier = "pro"

    # Update profile
    db.update_profile(
        user_id,
        {
            "tier": tier,
            "stripe_subscription_id": subscription_id,
            "billing_period_start": subscription.get("current_period_start"),
            "billing_period_end": subscription.get("current_period_end"),
        },
    )

    print(f"Subscription created for user {user_id}: {tier}")


async def handle_subscription_updated(subscription: dict) -> None:
    """Handle subscription updates (upgrades/downgrades)."""
    db = get_database()

    customer_id = subscription.get("customer")
    subscription_id = subscription.get("id")
    status_value = subscription.get("status")

    # Find user by customer ID
    result = (
        db.client.table("profiles").select("id").eq("stripe_customer_id", customer_id).execute()
    )

    if not result.data:
        print(f"No user found for customer {customer_id}")
        return

    user_id = result.data[0]["id"]

    # Determine tier from price
    items = subscription.get("items", {}).get("data", [])
    if items:
        price_id = items[0].get("price", {}).get("id")
        settings = get_settings()

        if price_id == settings.stripe_price_id_pro:
            tier = "pro"
        elif price_id == settings.stripe_price_id_unlimited:
            tier = "unlimited"
        else:
            tier = "pro"
    else:
        tier = "pro"

    # Handle canceled subscriptions
    if status_value in ("canceled", "unpaid"):
        tier = "free"

    # Update profile
    db.update_profile(
        user_id,
        {
            "tier": tier,
            "stripe_subscription_id": subscription_id if tier != "free" else None,
            "billing_period_start": subscription.get("current_period_start"),
            "billing_period_end": subscription.get("current_period_end"),
        },
    )

    print(f"Subscription updated for user {user_id}: {tier} ({status_value})")


async def handle_subscription_deleted(subscription: dict) -> None:
    """Handle subscription cancellation/deletion."""
    db = get_database()

    customer_id = subscription.get("customer")

    # Find user by customer ID
    result = (
        db.client.table("profiles").select("id").eq("stripe_customer_id", customer_id).execute()
    )

    if not result.data:
        print(f"No user found for customer {customer_id}")
        return

    user_id = result.data[0]["id"]

    # Downgrade to free tier
    db.update_profile(
        user_id,
        {
            "tier": "free",
            "stripe_subscription_id": None,
            "billing_period_start": None,
            "billing_period_end": None,
        },
    )

    print(f"Subscription deleted for user {user_id}, downgraded to free")


async def handle_invoice_paid(invoice: dict) -> None:
    """Handle successful invoice payment."""
    customer_id = invoice.get("customer")
    amount_paid = invoice.get("amount_paid", 0)

    print(f"Invoice paid for customer {customer_id}: ${amount_paid / 100:.2f}")

    # Could send receipt email, update analytics, etc.


async def handle_invoice_payment_failed(invoice: dict) -> None:
    """Handle failed invoice payment."""
    db = get_database()

    customer_id = invoice.get("customer")
    attempt_count = invoice.get("attempt_count", 0)

    print(f"Invoice payment failed for customer {customer_id} (attempt {attempt_count})")

    # Find user
    result = (
        db.client.table("profiles")
        .select("id, email")
        .eq("stripe_customer_id", customer_id)
        .execute()
    )

    if not result.data:
        return

    # After multiple failed attempts, could:
    # - Send warning email
    # - Temporarily restrict features
    # - Eventually downgrade to free

    if attempt_count >= 3:
        user_id = result.data[0]["id"]
        print(f"Multiple payment failures for user {user_id}, consider downgrade")
        # Uncomment to auto-downgrade after 3 failures:
        # db.update_profile(user_id, {"tier": "free"})
