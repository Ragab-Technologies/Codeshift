-- PyResolve Database Schema for Supabase
-- Run this in the Supabase SQL Editor to set up the billing infrastructure

-- ============================================
-- 1. PROFILES TABLE (extends Supabase auth.users)
-- ============================================
CREATE TABLE IF NOT EXISTS public.profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    email TEXT UNIQUE NOT NULL,
    full_name TEXT,
    tier TEXT NOT NULL DEFAULT 'free' CHECK (tier IN ('free', 'pro', 'unlimited', 'enterprise')),
    stripe_customer_id TEXT UNIQUE,
    stripe_subscription_id TEXT,
    billing_period_start TIMESTAMPTZ,
    billing_period_end TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Create index for faster lookups
CREATE INDEX IF NOT EXISTS idx_profiles_email ON public.profiles(email);
CREATE INDEX IF NOT EXISTS idx_profiles_stripe_customer ON public.profiles(stripe_customer_id);

-- ============================================
-- 2. API_KEYS TABLE
-- ============================================
CREATE TABLE IF NOT EXISTS public.api_keys (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    name TEXT NOT NULL DEFAULT 'CLI Key',
    key_prefix TEXT NOT NULL,  -- First 8 chars for identification (e.g., "pyr_abc1")
    key_hash TEXT NOT NULL,     -- SHA-256 hash of full key
    scopes TEXT[] NOT NULL DEFAULT ARRAY['read', 'write'],
    revoked BOOLEAN NOT NULL DEFAULT FALSE,
    revoked_at TIMESTAMPTZ,
    last_used_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_api_keys_user ON public.api_keys(user_id);
CREATE INDEX IF NOT EXISTS idx_api_keys_prefix ON public.api_keys(key_prefix);
CREATE INDEX IF NOT EXISTS idx_api_keys_hash ON public.api_keys(key_hash);
CREATE UNIQUE INDEX IF NOT EXISTS idx_api_keys_unique_hash ON public.api_keys(key_hash) WHERE NOT revoked;

-- ============================================
-- 3. USAGE_EVENTS TABLE
-- ============================================
CREATE TABLE IF NOT EXISTS public.usage_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    event_type TEXT NOT NULL CHECK (event_type IN ('file_migrated', 'llm_call', 'scan', 'apply')),
    library TEXT,  -- Which library was migrated (pydantic, fastapi, etc.)
    quantity INTEGER NOT NULL DEFAULT 1,
    metadata JSONB DEFAULT '{}',
    billing_period TEXT NOT NULL,  -- Format: "YYYY-MM"
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Create indexes for efficient querying
CREATE INDEX IF NOT EXISTS idx_usage_events_user ON public.usage_events(user_id);
CREATE INDEX IF NOT EXISTS idx_usage_events_period ON public.usage_events(billing_period);
CREATE INDEX IF NOT EXISTS idx_usage_events_user_period ON public.usage_events(user_id, billing_period);
CREATE INDEX IF NOT EXISTS idx_usage_events_type ON public.usage_events(event_type);

-- ============================================
-- 4. MONTHLY_USAGE VIEW
-- ============================================
CREATE OR REPLACE VIEW public.monthly_usage AS
SELECT
    user_id,
    billing_period,
    SUM(CASE WHEN event_type = 'file_migrated' THEN quantity ELSE 0 END) AS files_migrated,
    SUM(CASE WHEN event_type = 'llm_call' THEN quantity ELSE 0 END) AS llm_calls,
    SUM(CASE WHEN event_type = 'scan' THEN quantity ELSE 0 END) AS scans,
    SUM(CASE WHEN event_type = 'apply' THEN quantity ELSE 0 END) AS applies,
    COUNT(*) AS total_events
FROM public.usage_events
GROUP BY user_id, billing_period;

-- ============================================
-- 5. HELPER FUNCTIONS
-- ============================================

-- Function: Get current usage for a user
CREATE OR REPLACE FUNCTION public.get_current_usage(p_user_id UUID)
RETURNS TABLE (
    files_migrated BIGINT,
    llm_calls BIGINT,
    scans BIGINT,
    applies BIGINT
)
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    RETURN QUERY
    SELECT
        COALESCE(m.files_migrated, 0)::BIGINT,
        COALESCE(m.llm_calls, 0)::BIGINT,
        COALESCE(m.scans, 0)::BIGINT,
        COALESCE(m.applies, 0)::BIGINT
    FROM public.monthly_usage m
    WHERE m.user_id = p_user_id
      AND m.billing_period = TO_CHAR(NOW(), 'YYYY-MM');
END;
$$;

-- Function: Check if user has quota remaining
CREATE OR REPLACE FUNCTION public.check_quota(
    p_user_id UUID,
    p_event_type TEXT,
    p_quantity INTEGER DEFAULT 1
)
RETURNS BOOLEAN
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_tier TEXT;
    v_limit INTEGER;
    v_current_usage BIGINT;
BEGIN
    -- Get user's tier
    SELECT tier INTO v_tier FROM public.profiles WHERE id = p_user_id;

    IF v_tier IS NULL THEN
        RETURN FALSE;
    END IF;

    -- Set limits based on tier
    IF p_event_type = 'file_migrated' THEN
        v_limit := CASE v_tier
            WHEN 'free' THEN 100
            WHEN 'pro' THEN 1000
            WHEN 'unlimited' THEN 999999999
            WHEN 'enterprise' THEN 999999999
            ELSE 100
        END;
    ELSIF p_event_type = 'llm_call' THEN
        v_limit := CASE v_tier
            WHEN 'free' THEN 50
            WHEN 'pro' THEN 500
            WHEN 'unlimited' THEN 999999999
            WHEN 'enterprise' THEN 999999999
            ELSE 50
        END;
    ELSE
        -- No limits on scans/applies
        RETURN TRUE;
    END IF;

    -- Get current usage
    SELECT COALESCE(
        (SELECT SUM(quantity) FROM public.usage_events
         WHERE user_id = p_user_id
           AND event_type = p_event_type
           AND billing_period = TO_CHAR(NOW(), 'YYYY-MM')),
        0
    ) INTO v_current_usage;

    RETURN (v_current_usage + p_quantity) <= v_limit;
END;
$$;

-- Function: Create API key (returns the key prefix for storage)
CREATE OR REPLACE FUNCTION public.create_api_key(
    p_user_id UUID,
    p_key_prefix TEXT,
    p_key_hash TEXT,
    p_name TEXT DEFAULT 'CLI Key'
)
RETURNS UUID
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_key_id UUID;
BEGIN
    INSERT INTO public.api_keys (user_id, key_prefix, key_hash, name)
    VALUES (p_user_id, p_key_prefix, p_key_hash, p_name)
    RETURNING id INTO v_key_id;

    RETURN v_key_id;
END;
$$;

-- Function: Validate API key (returns user_id if valid)
CREATE OR REPLACE FUNCTION public.validate_api_key(p_key_hash TEXT)
RETURNS UUID
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_user_id UUID;
    v_key_id UUID;
BEGIN
    SELECT user_id, id INTO v_user_id, v_key_id
    FROM public.api_keys
    WHERE key_hash = p_key_hash
      AND revoked = FALSE
      AND (expires_at IS NULL OR expires_at > NOW());

    IF v_user_id IS NOT NULL THEN
        -- Update last_used_at
        UPDATE public.api_keys SET last_used_at = NOW() WHERE id = v_key_id;
    END IF;

    RETURN v_user_id;
END;
$$;

-- ============================================
-- 6. ROW LEVEL SECURITY POLICIES
-- ============================================

-- Enable RLS on all tables
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.api_keys ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.usage_events ENABLE ROW LEVEL SECURITY;

-- Profiles: Users can read/update their own profile
CREATE POLICY profiles_select ON public.profiles
    FOR SELECT USING (auth.uid() = id);

CREATE POLICY profiles_update ON public.profiles
    FOR UPDATE USING (auth.uid() = id);

-- API Keys: Users can manage their own keys
CREATE POLICY api_keys_select ON public.api_keys
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY api_keys_insert ON public.api_keys
    FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY api_keys_update ON public.api_keys
    FOR UPDATE USING (auth.uid() = user_id);

-- Usage Events: Users can read their own events
CREATE POLICY usage_events_select ON public.usage_events
    FOR SELECT USING (auth.uid() = user_id);

-- Service role can do everything (for API server)
CREATE POLICY profiles_service ON public.profiles
    FOR ALL USING (auth.jwt() ->> 'role' = 'service_role');

CREATE POLICY api_keys_service ON public.api_keys
    FOR ALL USING (auth.jwt() ->> 'role' = 'service_role');

CREATE POLICY usage_events_service ON public.usage_events
    FOR ALL USING (auth.jwt() ->> 'role' = 'service_role');

-- ============================================
-- 7. TRIGGERS
-- ============================================

-- Auto-update updated_at on profiles
CREATE OR REPLACE FUNCTION public.update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER profiles_updated_at
    BEFORE UPDATE ON public.profiles
    FOR EACH ROW
    EXECUTE FUNCTION public.update_updated_at();

-- Auto-create profile when user signs up
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO public.profiles (id, email, full_name)
    VALUES (
        NEW.id,
        NEW.email,
        COALESCE(NEW.raw_user_meta_data ->> 'full_name', '')
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Trigger for new user signup (if not exists)
DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW
    EXECUTE FUNCTION public.handle_new_user();

-- ============================================
-- 8. GRANT PERMISSIONS
-- ============================================

-- Grant usage on schema
GRANT USAGE ON SCHEMA public TO anon, authenticated;

-- Grant access to tables
GRANT SELECT, INSERT, UPDATE ON public.profiles TO authenticated;
GRANT SELECT, INSERT, UPDATE ON public.api_keys TO authenticated;
GRANT SELECT ON public.usage_events TO authenticated;
GRANT ALL ON public.usage_events TO service_role;

-- Grant access to functions
GRANT EXECUTE ON FUNCTION public.get_current_usage(UUID) TO authenticated;
GRANT EXECUTE ON FUNCTION public.check_quota(UUID, TEXT, INTEGER) TO authenticated;
GRANT EXECUTE ON FUNCTION public.validate_api_key(TEXT) TO anon, authenticated;
GRANT EXECUTE ON FUNCTION public.create_api_key(UUID, TEXT, TEXT, TEXT) TO authenticated;
