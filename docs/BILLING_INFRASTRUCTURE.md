# Billing Infrastructure Implementation Guide

This guide covers implementing user management, usage tracking, and payments for PyResolve using a simplified SaaS stack.

## Tech Stack

| Component | Service | Purpose | Cost |
| --------- | ------- | ------- | ---- |
| Auth + Database | **Supabase** | Users, API keys, usage tracking | Free → $25/mo |
| Payments | **Stripe** | Subscriptions, billing | 2.9% + $0.30/txn |
| Hosting | **Vercel** or **Railway** | API hosting | Free → $20/mo |

**Why this stack:**

- **2 services instead of 3** - Supabase handles both auth and database
- **Free tiers** - Can launch without upfront costs
- **Scales well** - Battle-tested infrastructure
- **Simple** - Less integration code, one dashboard for users + data

---

## Architecture

```text
┌─────────────────────────────────────────────────────────────────┐
│                        PyResolve CLI                            │
│                                                                 │
│  $ pyresolve upgrade pydantic --target 2.0                      │
│                                                                 │
│  Config: ~/.pyresolve/config.toml                               │
│  api_key = "pyr_live_abc123..."                                 │
└─────────────────────┬───────────────────────────────────────────┘
                      │ API Request + API Key
                      ▼
┌─────────────────────────────────────────────────────────────────┐
│                  PyResolve API (FastAPI)                        │
│                  api.pyresolve.dev                              │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ Middleware: Validate API Key → Get User                  │  │
│  └──────────────────────────────────────────────────────────┘  │
│                              │                                  │
│  ┌──────────────┐  ┌────────▼───────┐  ┌──────────────────┐   │
│  │ /auth        │  │ /migrate       │  │ /usage           │   │
│  │ - signup     │  │ - check quota  │  │ - get stats      │   │
│  │ - api-keys   │  │ - run migration│  │ - billing portal │   │
│  └──────────────┘  │ - log usage    │  └──────────────────┘   │
│                    └────────────────┘                          │
└─────────────────────────────────────────────────────────────────┘
                      │                              │
                      ▼                              ▼
       ┌─────────────────────────────┐      ┌──────────────┐
       │         Supabase            │      │   Stripe     │
       │                             │      │              │
       │  ┌─────────┐ ┌───────────┐  │      │ - Customers  │
       │  │  Auth   │ │ Database  │  │      │ - Subs       │
       │  │ (users) │ │ (api_keys │  │      │ - Invoices   │
       │  │         │ │  usage)   │  │      │ - Webhooks   │
       │  └─────────┘ └───────────┘  │      └──────────────┘
       └─────────────────────────────┘
```

---

## Step 1: Supabase Setup

### 1.1 Create Supabase Project

1. Go to [supabase.com](https://supabase.com) and create account
2. Create new project "pyresolve"
3. Note your project URL and keys from Settings → API

### 1.2 Environment Variables

```bash
# .env
SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
SUPABASE_SERVICE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

### 1.3 Database Schema

Run this in Supabase SQL Editor:

```sql
-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ============================================
-- Users Profile Table (extends Supabase Auth)
-- ============================================
CREATE TABLE public.profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    email TEXT NOT NULL,
    name TEXT,
    plan TEXT DEFAULT 'free' CHECK (plan IN ('free', 'pro', 'unlimited', 'enterprise')),
    stripe_customer_id TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Auto-create profile on user signup
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO public.profiles (id, email, name)
    VALUES (
        NEW.id,
        NEW.email,
        COALESCE(NEW.raw_user_meta_data->>'name', split_part(NEW.email, '@', 1))
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

-- ============================================
-- API Keys Table
-- ============================================
CREATE TABLE public.api_keys (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    key_hash TEXT NOT NULL,
    key_prefix TEXT NOT NULL,  -- "pyr_live_abc123" (first 20 chars for display)
    name TEXT DEFAULT 'Default',
    last_used_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    revoked_at TIMESTAMPTZ,

    CONSTRAINT unique_key_prefix UNIQUE (key_prefix)
);

CREATE INDEX idx_api_keys_prefix ON public.api_keys(key_prefix) WHERE revoked_at IS NULL;
CREATE INDEX idx_api_keys_user ON public.api_keys(user_id);

-- ============================================
-- Usage Events Table
-- ============================================
CREATE TABLE public.usage_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    event_type TEXT NOT NULL,  -- 'migration', 'scan', 'llm_call'
    library TEXT,              -- 'pydantic', 'fastapi', etc.
    tier TEXT,                 -- 'tier1', 'tier2', 'tier3'
    files_changed INTEGER DEFAULT 0,
    tokens_used INTEGER DEFAULT 0,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_usage_user_month ON public.usage_events (
    user_id,
    DATE_TRUNC('month', created_at)
);

-- ============================================
-- Monthly Usage View
-- ============================================
CREATE OR REPLACE VIEW public.monthly_usage AS
SELECT
    user_id,
    DATE_TRUNC('month', created_at) AS month,
    COUNT(*) FILTER (WHERE event_type = 'migration') AS migrations,
    COUNT(*) FILTER (WHERE tier = 'tier1') AS tier1_migrations,
    COUNT(*) FILTER (WHERE tier IN ('tier2', 'tier3')) AS llm_migrations,
    COALESCE(SUM(tokens_used), 0) AS total_tokens,
    COALESCE(SUM(files_changed), 0) AS total_files_changed
FROM public.usage_events
GROUP BY user_id, DATE_TRUNC('month', created_at);

-- ============================================
-- Helper Functions
-- ============================================

-- Generate a new API key for a user
CREATE OR REPLACE FUNCTION public.create_api_key(p_name TEXT DEFAULT 'Default')
RETURNS TABLE (api_key TEXT, key_prefix TEXT) AS $$
DECLARE
    v_user_id UUID;
    v_key TEXT;
    v_prefix TEXT;
    v_hash TEXT;
BEGIN
    -- Get current user from Supabase auth
    v_user_id := auth.uid();
    IF v_user_id IS NULL THEN
        RAISE EXCEPTION 'Not authenticated';
    END IF;

    -- Generate random key: pyr_live_<32 chars>
    v_key := 'pyr_live_' || encode(gen_random_bytes(24), 'hex');
    v_prefix := substring(v_key, 1, 20);
    v_hash := crypt(v_key, gen_salt('bf'));

    INSERT INTO public.api_keys (user_id, key_hash, key_prefix, name)
    VALUES (v_user_id, v_hash, v_prefix, p_name);

    RETURN QUERY SELECT v_key AS api_key, v_prefix AS key_prefix;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Validate API key and return user info
CREATE OR REPLACE FUNCTION public.validate_api_key(p_api_key TEXT)
RETURNS TABLE (
    user_id UUID,
    email TEXT,
    plan TEXT,
    stripe_customer_id TEXT
) AS $$
DECLARE
    v_prefix TEXT;
    v_record RECORD;
BEGIN
    v_prefix := substring(p_api_key, 1, 20);

    SELECT ak.*, p.email, p.plan, p.stripe_customer_id
    INTO v_record
    FROM public.api_keys ak
    JOIN public.profiles p ON p.id = ak.user_id
    WHERE ak.key_prefix = v_prefix
      AND ak.revoked_at IS NULL;

    IF v_record IS NULL THEN
        RETURN;
    END IF;

    -- Verify hash
    IF v_record.key_hash = crypt(p_api_key, v_record.key_hash) THEN
        -- Update last used
        UPDATE public.api_keys SET last_used_at = NOW() WHERE id = v_record.id;

        RETURN QUERY SELECT
            v_record.user_id,
            v_record.email,
            v_record.plan,
            v_record.stripe_customer_id;
    END IF;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Get current month usage for a user
CREATE OR REPLACE FUNCTION public.get_current_usage(p_user_id UUID)
RETURNS TABLE (
    migrations BIGINT,
    tier1_migrations BIGINT,
    llm_migrations BIGINT,
    total_tokens BIGINT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        COALESCE(mu.migrations, 0),
        COALESCE(mu.tier1_migrations, 0),
        COALESCE(mu.llm_migrations, 0),
        COALESCE(mu.total_tokens, 0)
    FROM public.monthly_usage mu
    WHERE mu.user_id = p_user_id
      AND mu.month = DATE_TRUNC('month', NOW());
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- ============================================
-- Row Level Security
-- ============================================
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.api_keys ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.usage_events ENABLE ROW LEVEL SECURITY;

-- Profiles: users can only see/edit their own profile
CREATE POLICY "Users can view own profile"
    ON public.profiles FOR SELECT
    USING (auth.uid() = id);

CREATE POLICY "Users can update own profile"
    ON public.profiles FOR UPDATE
    USING (auth.uid() = id);

-- API Keys: users can only manage their own keys
CREATE POLICY "Users can view own API keys"
    ON public.api_keys FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own API keys"
    ON public.api_keys FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own API keys"
    ON public.api_keys FOR UPDATE
    USING (auth.uid() = user_id);

-- Usage: users can only see their own usage
CREATE POLICY "Users can view own usage"
    ON public.usage_events FOR SELECT
    USING (auth.uid() = user_id);

-- Service role can do everything (for API backend)
CREATE POLICY "Service role full access to profiles"
    ON public.profiles FOR ALL
    USING (auth.role() = 'service_role');

CREATE POLICY "Service role full access to api_keys"
    ON public.api_keys FOR ALL
    USING (auth.role() = 'service_role');

CREATE POLICY "Service role full access to usage"
    ON public.usage_events FOR ALL
    USING (auth.role() = 'service_role');
```

---

## Step 2: Stripe Setup

### 2.1 Create Stripe Account

1. Go to [stripe.com](https://stripe.com) and create account
2. Get API keys from Dashboard → Developers → API Keys

### 2.2 Create Products and Prices

In Stripe Dashboard → Products, create:

| Product | Price | Price ID |
| ------- | ----- | -------- |
| PyResolve Pro | $19/month | `price_pro_xxxxx` |
| PyResolve Unlimited | $49/month | `price_unlimited_xxxxx` |

Or use Stripe CLI:

```bash
stripe products create --name="PyResolve Pro" \
  --description="50 migrations/month, all tiers"

stripe prices create \
  --product=prod_xxxxx \
  --unit-amount=1900 \
  --currency=usd \
  --recurring[interval]=month
```

### 2.3 Environment Variables

```bash
# .env (add to existing)
STRIPE_SECRET_KEY=sk_live_xxxxx
STRIPE_WEBHOOK_SECRET=whsec_xxxxx
STRIPE_PRICE_PRO=price_xxxxx
STRIPE_PRICE_UNLIMITED=price_xxxxx
```

---

## Step 3: Python API Implementation

### 3.1 Install Dependencies

```bash
pip install fastapi uvicorn supabase stripe python-dotenv
```

### 3.2 Project Structure

```
pyresolve/
├── api/
│   ├── __init__.py
│   ├── main.py          # FastAPI app
│   ├── auth.py          # API key validation
│   ├── billing.py       # Stripe integration
│   ├── database.py      # Supabase client
│   └── webhooks.py      # Stripe webhooks
└── cli/
    └── ...
```

### 3.3 Database Client

```python
# pyresolve/api/database.py
import os
from supabase import create_client, Client
from functools import lru_cache

@lru_cache()
def get_supabase() -> Client:
    """Get Supabase client (singleton)."""
    return create_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_SERVICE_KEY"]
    )

# Plan limits configuration
PLAN_LIMITS = {
    "free": {"migrations": 5, "llm_allowed": False},
    "pro": {"migrations": 50, "llm_allowed": True},
    "unlimited": {"migrations": float("inf"), "llm_allowed": True},
    "enterprise": {"migrations": float("inf"), "llm_allowed": True},
}
```

### 3.4 Authentication

```python
# pyresolve/api/auth.py
from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader
from codeshift.api.database import get_supabase

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def get_current_user(api_key: str = Security(api_key_header)) -> dict:
    """Validate API key and return user."""
    if not api_key:
        raise HTTPException(
            status_code=401,
            detail="API key required. Get one at https://pyresolve.dev"
        )

    if not api_key.startswith("pyr_live_"):
        raise HTTPException(
            status_code=401,
            detail="Invalid API key format"
        )

    supabase = get_supabase()

    # Call the validation function
    result = supabase.rpc("validate_api_key", {"p_api_key": api_key}).execute()

    if not result.data or len(result.data) == 0:
        raise HTTPException(
            status_code=401,
            detail="Invalid or revoked API key"
        )

    return result.data[0]


async def get_optional_user(api_key: str = Security(api_key_header)) -> dict | None:
    """Get user if API key provided, None otherwise."""
    if not api_key:
        return None

    try:
        return await get_current_user(api_key)
    except HTTPException:
        return None
```

### 3.5 Billing Logic

```python
# pyresolve/api/billing.py
import os
import stripe
from codeshift.api.database import get_supabase, PLAN_LIMITS

stripe.api_key = os.environ["STRIPE_SECRET_KEY"]


async def get_quota(user: dict) -> dict:
    """Get user's current quota status."""
    plan = user.get("plan", "free")
    limits = PLAN_LIMITS[plan]

    supabase = get_supabase()
    result = supabase.rpc("get_current_usage", {"p_user_id": user["user_id"]}).execute()

    usage = result.data[0] if result.data else {
        "migrations": 0,
        "tier1_migrations": 0,
        "llm_migrations": 0
    }

    migrations_used = usage["migrations"]
    migrations_limit = limits["migrations"]

    return {
        "plan": plan,
        "migrations_used": migrations_used,
        "migrations_limit": migrations_limit if migrations_limit != float("inf") else "unlimited",
        "migrations_remaining": (migrations_limit - migrations_used) if migrations_limit != float("inf") else "unlimited",
        "llm_allowed": limits["llm_allowed"],
        "can_migrate": migrations_used < migrations_limit,
    }


async def create_checkout_session(user: dict, price_id: str) -> str:
    """Create Stripe checkout session."""
    supabase = get_supabase()

    # Get or create Stripe customer
    customer_id = user.get("stripe_customer_id")

    if not customer_id:
        customer = stripe.Customer.create(
            email=user["email"],
            metadata={"user_id": str(user["user_id"])}
        )
        customer_id = customer.id

        # Save customer ID to profile
        supabase.table("profiles") \
            .update({"stripe_customer_id": customer_id}) \
            .eq("id", user["user_id"]) \
            .execute()

    session = stripe.checkout.Session.create(
        customer=customer_id,
        mode="subscription",
        line_items=[{"price": price_id, "quantity": 1}],
        success_url="https://pyresolve.dev/billing?success=true",
        cancel_url="https://pyresolve.dev/billing?canceled=true",
        metadata={"user_id": str(user["user_id"])}
    )

    return session.url


async def create_portal_session(user: dict) -> str:
    """Create Stripe billing portal session."""
    if not user.get("stripe_customer_id"):
        raise ValueError("No billing account found")

    session = stripe.billing_portal.Session.create(
        customer=user["stripe_customer_id"],
        return_url="https://pyresolve.dev/billing"
    )

    return session.url


async def log_usage(user_id: str, event_type: str, **kwargs):
    """Log a usage event."""
    supabase = get_supabase()

    supabase.table("usage_events").insert({
        "user_id": user_id,
        "event_type": event_type,
        "library": kwargs.get("library"),
        "tier": kwargs.get("tier"),
        "files_changed": kwargs.get("files_changed", 0),
        "tokens_used": kwargs.get("tokens_used", 0),
        "metadata": kwargs.get("metadata", {})
    }).execute()
```

### 3.6 Webhook Handler

```python
# pyresolve/api/webhooks.py
import os
import stripe
from fastapi import APIRouter, Request, HTTPException
from codeshift.api.database import get_supabase

router = APIRouter()

PRICE_TO_PLAN = {
    os.environ.get("STRIPE_PRICE_PRO", ""): "pro",
    os.environ.get("STRIPE_PRICE_UNLIMITED", ""): "unlimited",
}


@router.post("/webhooks/stripe")
async def stripe_webhook(request: Request):
    """Handle Stripe webhook events."""
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, os.environ["STRIPE_WEBHOOK_SECRET"]
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    supabase = get_supabase()

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        customer_id = session["customer"]

        # Get subscription to find the price/plan
        subscription = stripe.Subscription.retrieve(session["subscription"])
        price_id = subscription["items"]["data"][0]["price"]["id"]
        plan = PRICE_TO_PLAN.get(price_id, "pro")

        # Update user's plan
        supabase.table("profiles") \
            .update({"plan": plan}) \
            .eq("stripe_customer_id", customer_id) \
            .execute()

    elif event["type"] == "customer.subscription.updated":
        subscription = event["data"]["object"]
        customer_id = subscription["customer"]
        price_id = subscription["items"]["data"][0]["price"]["id"]

        if subscription["status"] == "active":
            plan = PRICE_TO_PLAN.get(price_id, "pro")
        else:
            plan = "free"

        supabase.table("profiles") \
            .update({"plan": plan}) \
            .eq("stripe_customer_id", customer_id) \
            .execute()

    elif event["type"] == "customer.subscription.deleted":
        customer_id = event["data"]["object"]["customer"]

        # Downgrade to free
        supabase.table("profiles") \
            .update({"plan": "free"}) \
            .eq("stripe_customer_id", customer_id) \
            .execute()

    return {"status": "ok"}
```

### 3.7 FastAPI Application

```python
# pyresolve/api/main.py
import os
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from codeshift.api.auth import get_current_user, get_optional_user
from codeshift.api.billing import get_quota, create_checkout_session, create_portal_session, log_usage
from codeshift.api.webhooks import router as webhook_router

app = FastAPI(
    title="PyResolve API",
    description="API for PyResolve migration tool",
    version="0.1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://pyresolve.dev", "http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(webhook_router)


# ============================================
# Models
# ============================================

class UsageEvent(BaseModel):
    event_type: str
    library: str | None = None
    tier: str | None = None
    files_changed: int = 0
    tokens_used: int = 0


class CheckoutRequest(BaseModel):
    plan: str  # "pro" or "unlimited"


# ============================================
# Endpoints
# ============================================

@app.get("/")
async def root():
    return {"service": "PyResolve API", "version": "0.1.0"}


@app.get("/quota")
async def quota_endpoint(user: dict = Depends(get_current_user)):
    """Get current usage quota."""
    return await get_quota(user)


@app.post("/usage")
async def usage_endpoint(
    event: UsageEvent,
    user: dict = Depends(get_current_user)
):
    """Record a usage event."""
    await log_usage(
        user_id=user["user_id"],
        event_type=event.event_type,
        library=event.library,
        tier=event.tier,
        files_changed=event.files_changed,
        tokens_used=event.tokens_used
    )
    return {"status": "recorded"}


@app.get("/me")
async def me_endpoint(user: dict = Depends(get_current_user)):
    """Get current user info and quota."""
    quota = await get_quota(user)
    return {
        "user_id": str(user["user_id"]),
        "email": user["email"],
        "plan": user["plan"],
        "quota": quota
    }


@app.post("/billing/checkout")
async def checkout_endpoint(
    request: CheckoutRequest,
    user: dict = Depends(get_current_user)
):
    """Create Stripe checkout session."""
    price_map = {
        "pro": os.environ["STRIPE_PRICE_PRO"],
        "unlimited": os.environ["STRIPE_PRICE_UNLIMITED"],
    }

    if request.plan not in price_map:
        raise HTTPException(status_code=400, detail="Invalid plan. Use 'pro' or 'unlimited'")

    url = await create_checkout_session(user, price_map[request.plan])
    return {"checkout_url": url}


@app.get("/billing/portal")
async def portal_endpoint(user: dict = Depends(get_current_user)):
    """Get Stripe billing portal URL."""
    if not user.get("stripe_customer_id"):
        raise HTTPException(
            status_code=400,
            detail="No billing account. Subscribe first at https://pyresolve.dev/pricing"
        )

    url = await create_portal_session(user)
    return {"portal_url": url}


# ============================================
# Health Check
# ============================================

@app.get("/health")
async def health():
    return {"status": "healthy"}
```

---

## Step 4: CLI Integration

### 4.1 Add Auth Commands

```python
# pyresolve/cli/auth.py
import os
import click
import httpx
from pathlib import Path

CONFIG_DIR = Path.home() / ".pyresolve"
CONFIG_FILE = CONFIG_DIR / "config.toml"
API_BASE = os.environ.get("PYRESOLVE_API_URL", "https://api.pyresolve.dev")


def get_api_key() -> str | None:
    """Get API key from environment or config."""
    # Environment takes priority
    if key := os.environ.get("PYRESOLVE_API_KEY"):
        return key

    # Check config file
    if CONFIG_FILE.exists():
        import toml
        config = toml.load(CONFIG_FILE)
        return config.get("api_key")

    return None


def save_api_key(api_key: str):
    """Save API key to config file."""
    import toml

    CONFIG_DIR.mkdir(exist_ok=True)

    config = {}
    if CONFIG_FILE.exists():
        config = toml.load(CONFIG_FILE)

    config["api_key"] = api_key

    with open(CONFIG_FILE, "w") as f:
        toml.dump(config, f)

    # Secure the file
    os.chmod(CONFIG_FILE, 0o600)


@click.command()
@click.option("--key", prompt="Enter your API key", hide_input=True, help="Your PyResolve API key")
def login(key: str):
    """Authenticate with PyResolve."""
    if not key.startswith("pyr_live_"):
        click.echo("❌ Invalid API key format. Keys start with 'pyr_live_'")
        click.echo("   Get your key at https://pyresolve.dev/settings")
        return

    # Verify key with API
    try:
        with httpx.Client() as client:
            response = client.get(
                f"{API_BASE}/me",
                headers={"X-API-Key": key},
                timeout=10.0
            )

        if response.status_code == 200:
            user = response.json()
            save_api_key(key)
            click.echo(f"✓ Authenticated as {user['email']}")
            click.echo(f"  Plan: {user['plan']}")
            click.echo(f"  Migrations remaining: {user['quota']['migrations_remaining']}")
        else:
            click.echo("❌ Invalid API key")
            click.echo("   Get your key at https://pyresolve.dev/settings")

    except httpx.RequestError as e:
        click.echo(f"❌ Connection error: {e}")


@click.command()
def logout():
    """Remove saved credentials."""
    if CONFIG_FILE.exists():
        os.remove(CONFIG_FILE)
        click.echo("✓ Logged out successfully")
    else:
        click.echo("Not logged in")


@click.command()
def status():
    """Show current authentication status and quota."""
    api_key = get_api_key()

    if not api_key:
        click.echo("Not logged in")
        click.echo("Run: pyresolve login")
        return

    try:
        with httpx.Client() as client:
            response = client.get(
                f"{API_BASE}/me",
                headers={"X-API-Key": api_key},
                timeout=10.0
            )

        if response.status_code == 200:
            user = response.json()
            quota = user["quota"]

            click.echo(f"Email: {user['email']}")
            click.echo(f"Plan:  {user['plan'].upper()}")
            click.echo(f"")
            click.echo(f"This month:")
            click.echo(f"  Migrations: {quota['migrations_used']}/{quota['migrations_limit']}")
            click.echo(f"  LLM access: {'✓' if quota['llm_allowed'] else '✗ (upgrade to Pro)'}")
        else:
            click.echo("❌ Invalid or expired API key")
            click.echo("Run: pyresolve login")

    except httpx.RequestError as e:
        click.echo(f"❌ Connection error: {e}")
```

### 4.2 Add Quota Check to Migrations

```python
# pyresolve/cli/migrate.py (add to existing)
import httpx
from codeshift.cli.auth import get_api_key, API_BASE


def check_quota_before_migration(tier: str) -> bool:
    """
    Check if user can run migration.
    Returns True if allowed, False otherwise.
    """
    api_key = get_api_key()

    # Tier 1 (AST-only) is free without auth
    if tier == "tier1" and not api_key:
        return True

    # LLM tiers require auth
    if tier in ("tier2", "tier3") and not api_key:
        click.echo("⚠️  LLM-powered migrations require authentication")
        click.echo("")
        click.echo("Options:")
        click.echo("  1. Run: pyresolve login")
        click.echo("  2. Get free account: https://pyresolve.dev")
        click.echo("  3. Use --tier1-only flag for AST-only migration")
        return False

    if not api_key:
        return True  # Allow unauthenticated tier1

    # Check quota with API
    try:
        with httpx.Client() as client:
            response = client.get(
                f"{API_BASE}/quota",
                headers={"X-API-Key": api_key},
                timeout=10.0
            )

        if response.status_code == 401:
            click.echo("❌ Invalid API key. Run: pyresolve login")
            return False

        quota = response.json()

        # Check migration limit
        if not quota["can_migrate"]:
            click.echo(f"❌ Monthly limit reached ({quota['migrations_limit']} migrations)")
            click.echo("   Upgrade at https://pyresolve.dev/pricing")
            return False

        # Check LLM access
        if tier in ("tier2", "tier3") and not quota["llm_allowed"]:
            click.echo("❌ LLM migrations require Pro plan")
            click.echo("   Upgrade at https://pyresolve.dev/pricing")
            click.echo("   Or use --tier1-only for free AST migration")
            return False

        # Show remaining quota
        remaining = quota["migrations_remaining"]
        if remaining != "unlimited":
            click.echo(f"📊 Quota: {remaining} migrations remaining this month")

        return True

    except httpx.RequestError:
        # Allow migration if API is unreachable (offline mode)
        click.echo("⚠️  Could not reach API, proceeding in offline mode")
        return True


def log_migration_usage(library: str, tier: str, files_changed: int):
    """Log usage after successful migration."""
    api_key = get_api_key()
    if not api_key:
        return

    try:
        with httpx.Client() as client:
            client.post(
                f"{API_BASE}/usage",
                headers={"X-API-Key": api_key},
                json={
                    "event_type": "migration",
                    "library": library,
                    "tier": tier,
                    "files_changed": files_changed
                },
                timeout=10.0
            )
    except httpx.RequestError:
        pass  # Silent fail for usage logging
```

---

## Step 5: Deployment

### Option A: Railway (Recommended)

```bash
# Install Railway CLI
npm i -g @railway/cli

# Login and init
railway login
railway init

# Add environment variables
railway variables set SUPABASE_URL=xxx
railway variables set SUPABASE_SERVICE_KEY=xxx
railway variables set STRIPE_SECRET_KEY=xxx
railway variables set STRIPE_WEBHOOK_SECRET=xxx
railway variables set STRIPE_PRICE_PRO=xxx
railway variables set STRIPE_PRICE_UNLIMITED=xxx

# Deploy
railway up
```

### Option B: Vercel

Create `vercel.json`:

```json
{
  "builds": [
    {
      "src": "pyresolve/api/main.py",
      "use": "@vercel/python"
    }
  ],
  "routes": [
    {
      "src": "/(.*)",
      "dest": "pyresolve/api/main.py"
    }
  ]
}
```

### Option C: Docker

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY pyresolve/ pyresolve/

EXPOSE 8000

CMD ["uvicorn", "pyresolve.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

## Environment Variables Summary

```bash
# Supabase
SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
SUPABASE_SERVICE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

# Stripe
STRIPE_SECRET_KEY=sk_live_xxxxx
STRIPE_WEBHOOK_SECRET=whsec_xxxxx
STRIPE_PRICE_PRO=price_xxxxx
STRIPE_PRICE_UNLIMITED=price_xxxxx

# App
PYRESOLVE_API_URL=https://api.pyresolve.dev
```

---

## Implementation Checklist

### Phase 1: Infrastructure

- [ ] Create Supabase project
- [ ] Run database schema SQL
- [ ] Create Stripe account
- [ ] Create Stripe products/prices
- [ ] Set up environment variables

### Phase 2: API

- [ ] Create FastAPI project structure
- [ ] Implement auth middleware
- [ ] Implement quota checking
- [ ] Implement usage logging
- [ ] Implement Stripe checkout/webhooks
- [ ] Deploy API

### Phase 3: CLI

- [ ] Add `pyresolve login` command
- [ ] Add `pyresolve logout` command
- [ ] Add `pyresolve status` command
- [ ] Add quota check before migrations
- [ ] Add usage logging after migrations

### Phase 4: Testing

- [ ] Test free tier (no auth, tier1 only)
- [ ] Test authenticated tier1
- [ ] Test quota enforcement
- [ ] Test upgrade flow
- [ ] Test subscription cancellation

---

## Cost Estimates

| Monthly Users | Supabase | Stripe Fees | Hosting | Total |
| ------------- | -------- | ----------- | ------- | ----- |
| 100 | Free | ~$5 | Free | ~$5 |
| 1,000 | Free | ~$50 | $20 | ~$70 |
| 10,000 | $25 | ~$500 | $50 | ~$575 |

Revenue at 10,000 users with 3% conversion at $19/mo = **$5,700 MRR**

Infrastructure cost = ~10% of revenue ✓
