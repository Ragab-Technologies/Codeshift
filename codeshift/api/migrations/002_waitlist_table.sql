-- ============================================
-- Waitlist Table for Landing Page Signups
-- ============================================

-- Create the waitlist table
CREATE TABLE IF NOT EXISTS public.waitlist (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    source TEXT DEFAULT 'landing_page',
    referrer TEXT,  -- Optional: track where they came from
    utm_source TEXT,  -- Optional: marketing campaign tracking
    utm_medium TEXT,
    utm_campaign TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Add comment for documentation
COMMENT ON TABLE public.waitlist IS 'Stores email signups from the landing page waitlist';

-- Enable Row Level Security
ALTER TABLE public.waitlist ENABLE ROW LEVEL SECURITY;

-- Policy: Allow anonymous users to insert (for landing page form submissions)
CREATE POLICY "Allow anonymous inserts" ON public.waitlist
    FOR INSERT
    TO anon
    WITH CHECK (true);

-- Policy: Only service role can read/update/delete (for admin access)
CREATE POLICY "Service role full access" ON public.waitlist
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Create index on email for faster duplicate checking
CREATE INDEX IF NOT EXISTS idx_waitlist_email ON public.waitlist(email);

-- Create index on created_at for sorting/filtering by signup date
CREATE INDEX IF NOT EXISTS idx_waitlist_created_at ON public.waitlist(created_at DESC);

-- Trigger to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_waitlist_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER waitlist_updated_at_trigger
    BEFORE UPDATE ON public.waitlist
    FOR EACH ROW
    EXECUTE FUNCTION update_waitlist_updated_at();

-- Grant permissions
GRANT INSERT ON public.waitlist TO anon;
GRANT ALL ON public.waitlist TO service_role;
