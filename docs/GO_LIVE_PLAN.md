# Codeshift Go-Live Plan

Complete checklist for making the repository public and launching the service.

---

## Phase 1: Pre-Launch Security Audit

### 1.1 Credential Rotation (CRITICAL)
Even though no secrets are in the current codebase, rotate all credentials before going public as a precaution:

- [ ] **Supabase**: Regenerate anon key and service role key in Project Settings > API
- [ ] **Stripe**: Roll API keys in Developers > API Keys (create new, update Replit, delete old)
- [ ] **Anthropic**: Regenerate API key at console.anthropic.com
- [ ] **Update Replit secrets** with all new credentials

### 1.2 Verify No Secrets in Git History
```bash
# Search for potential secrets in git history
git log -p --all -S 'sk_live' --  # Stripe live keys
git log -p --all -S 'sk_test' --  # Stripe test keys
git log -p --all -S 'sk-ant' --   # Anthropic keys
git log -p --all -S 'supabase' -- # Supabase URLs with keys
```

If anything is found, use `git filter-repo` to scrub history before making public.

---

## Phase 2: Infrastructure Setup

### 2.1 API URL
Using Replit deployment URL: `https://py-resolve.replit.app`

No custom domain needed for launch. Can add later if desired.

### 2.2 Supabase Production Setup
- [ ] Run migration SQL (`codeshift/api/migrations/001_initial_schema.sql`)
- [ ] Enable Row Level Security on all tables
- [ ] Configure auth settings (email confirmation, password requirements)
- [ ] Set up database backups (Supabase dashboard > Database > Backups)

### 2.3 Stripe Production Setup
- [ ] Create products in Stripe:
  - **Pro**: $19/month, Product ID needed for `STRIPE_PRICE_ID_PRO`
  - **Unlimited**: $49/month, Product ID needed for `STRIPE_PRICE_ID_UNLIMITED`
- [ ] Configure webhook endpoint: `https://py-resolve.replit.app/webhooks/stripe`
- [ ] Enable webhook events:
  - `checkout.session.completed`
  - `customer.subscription.created`
  - `customer.subscription.updated`
  - `customer.subscription.deleted`
  - `invoice.paid`
  - `invoice.payment_failed`
- [ ] Test with Stripe CLI locally first:
  ```bash
  stripe listen --forward-to localhost:8000/webhooks/stripe
  stripe trigger checkout.session.completed
  ```

### 2.4 Replit Production Configuration
- [ ] Verify all environment variables are set (see `.env.example`)
- [ ] Set `ENVIRONMENT=production`
- [ ] Enable always-on deployment
- [ ] Test health endpoint: `curl https://py-resolve.replit.app/health`

---

## Phase 3: Code Finalization

### 3.1 Version Bump
- [ ] Update version in `pyproject.toml` (currently 0.3.7)
- [ ] Update version in `codeshift/__init__.py` if separate
- [ ] Create git tag: `git tag -a v0.4.0 -m "Public release"`

### 3.2 PyPI Publication
```bash
# Build the package
pip install build twine
python -m build

# Upload to PyPI (need PyPI account and API token)
twine upload dist/*
```

- [ ] Verify installation works: `pip install codeshift`
- [ ] Test CLI: `codeshift --help`

### 3.3 Final Code Review
- [ ] All hardcoded URLs updated (done ✓)
- [ ] GitHub references point to Ragab-Technologies (done ✓)
- [ ] Rate limiting enabled (done ✓)
- [ ] No TODO comments with sensitive info
- [ ] README is accurate and up-to-date

---

## Phase 4: GitHub Repository

### 4.1 Repository Settings
- [ ] Change repository visibility to **Public**
- [ ] Enable GitHub Discussions
- [ ] Set up branch protection on `main`:
  - Require PR reviews
  - Require status checks to pass
  - No force pushes
- [ ] Add repository topics: `python`, `migration`, `pydantic`, `cli`, `ast`, `codemod`

### 4.2 GitHub Actions (CI/CD)
Create `.github/workflows/ci.yml`:
```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ['3.10', '3.11', '3.12']
    steps:
      - uses: actions/checkout@v4
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
      - name: Install dependencies
        run: pip install -e ".[dev]"
      - name: Lint
        run: |
          ruff check .
          black --check .
      - name: Test
        run: pytest --cov=codeshift
```

### 4.3 Release Automation
Create `.github/workflows/release.yml` for automatic PyPI publishing on tags.

---

## Phase 5: Launch Day

### 5.1 Pre-Launch Checklist (Morning)
- [ ] Verify Replit deployment is healthy
- [ ] Verify Stripe webhook is receiving events
- [ ] Verify Supabase is accessible
- [ ] Test full user flow:
  1. `pip install codeshift`
  2. `codeshift scan` (should work without auth)
  3. `codeshift login --device`
  4. `codeshift upgrade pydantic --target 2.5.0` (free tier, AST only)
  5. Upgrade to Pro via checkout
  6. Test LLM migration endpoint

### 5.2 Make Repository Public
```bash
# Via GitHub CLI
gh repo edit Ragab-Technologies/Codeshift --visibility public
```

### 5.3 Announcements
- [ ] Post on Twitter/X
- [ ] Post on LinkedIn
- [ ] Submit to Hacker News (Show HN)
- [ ] Post on Reddit r/Python
- [ ] Post on Dev.to
- [ ] Notify waitlist subscribers

### 5.4 Monitor
- [ ] Watch Stripe dashboard for first payments
- [ ] Monitor Replit logs for errors
- [ ] Check Supabase for new user signups
- [ ] Respond to GitHub issues quickly

---

## Phase 6: Post-Launch

### 6.1 First Week
- [ ] Monitor error rates and latency
- [ ] Respond to all GitHub issues within 24 hours
- [ ] Gather feedback from early users
- [ ] Fix any critical bugs immediately

### 6.2 First Month
- [ ] Analyze usage patterns
- [ ] Identify most-requested features
- [ ] Consider adding more Tier 1 library support based on demand
- [ ] Write blog post about the launch

---

## Environment Variables Reference

Required for production (set in Replit Secrets):

```
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_ANON_KEY=eyJ...
SUPABASE_SERVICE_ROLE_KEY=eyJ...
STRIPE_SECRET_KEY=sk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_PRICE_ID_PRO=price_...
STRIPE_PRICE_ID_UNLIMITED=price_...
ANTHROPIC_API_KEY=sk-ant-...
ENVIRONMENT=production
CODESHIFT_API_URL=https://py-resolve.replit.app
```

---

## Rollback Plan

If critical issues arise after launch:

1. **Revert to private**: `gh repo edit --visibility private`
2. **Revert code**: `git revert HEAD` or `git reset --hard <safe-commit>`
3. **Communicate**: Post on social media that you're fixing issues
4. **Fix and re-launch**: Address issues, then repeat Phase 5

---

## Success Metrics

Track these in the first 30 days:

| Metric | Target |
|--------|--------|
| GitHub stars | 100+ |
| PyPI downloads | 500+ |
| Registered users | 50+ |
| Paid subscribers | 5+ |
| GitHub issues responded to | 100% within 24h |
