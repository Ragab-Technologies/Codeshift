# Codeshift Master Plan

This document consolidates all goals from `docs/GO_TO_MARKET.md`, `docs/MONETIZATION.md`, and `docs/BILLING_INFRASTRUCTURE.md` into an actionable implementation plan.

---

## Current State Summary

**What Exists:**
- Core migration engine (AST transforms + LLM fallback)
- CLI with 7 commands: `scan`, `upgrade`, `upgrade-all`, `diff`, `apply`, `libraries`, `status`
- 5 Tier 1 libraries: Pydantic, FastAPI, SQLAlchemy, Pandas, Requests
- Knowledge base system that fetches from GitHub
- Tests (11 files, 138 tests passing)
- Landing page with GitHub Pages deployment
- MIT License
- Server-side LLM architecture: Tier 2/3 migrations routed through Codeshift API

**What's Missing:**
- Supabase/Stripe account setup (user action required)
- API deployment (user action required)
- Public release to PyPI
- Demo video/GIF for README

---

## Phase 1: Pre-Launch Foundation

### 1.1 Legal & Licensing
- [x] Add LICENSE file (MIT License - changed from ELv2)
- [x] Update pyproject.toml with correct license
- [x] Update README with license explanation
- [x] Add contact email for commercial licensing in README
- [x] Architecture: Server-side LLM calls protect monetization with open source code

### 1.2 Technical Readiness
- [x] Set up CI/CD pipeline (GitHub Actions)
  - [x] Run tests on PRs
  - [x] Run linting (ruff, black, mypy)
  - [x] Test on Python 3.9, 3.10, 3.11, 3.12
- [x] Increase test coverage (main modules >80%, overall 43%)
- [x] Create PyPI publish workflow
- [x] Create stable release v0.2.0-beta (version bumped to 0.2.0b1)
- [ ] Publish to TestPyPI first (trigger workflow manually)
- [ ] Publish to PyPI (trigger workflow after release)

### 1.3 Documentation
- [x] Add CONTRIBUTING.md
- [x] Add CODE_OF_CONDUCT.md
- [x] Create GitHub issue templates (bug, feature request)
- [x] Create PR template
- [x] Write "Getting Started" tutorial (docs/getting_started.md)
- [ ] Create demo video/GIF for README

---

## Phase 2: Billing Infrastructure (Supabase + Stripe)

### 2.1 Supabase Setup
- [x] Create Supabase project "codeshift" (schema ready in `codeshift/api/migrations/001_initial_schema.sql`)
- [x] Run database schema SQL:
  - `profiles` table (extends Supabase auth)
  - `api_keys` table with hashing
  - `usage_events` table
  - `monthly_usage` view
  - Helper functions: `create_api_key`, `validate_api_key`, `get_current_usage`
  - Row Level Security policies
- [ ] Note project URL and keys (user action required)

### 2.2 Stripe Setup
- [x] Create Stripe account (user action required)
- [x] Create products and prices (user action required):
  - Codeshift Pro: $19/month
  - Codeshift Unlimited: $49/month
- [x] Configure webhook endpoint (user action required)

### 2.3 FastAPI Billing API
- [x] Create `codeshift/api/` directory structure:
  - `main.py` - FastAPI app
  - `auth.py` - API key validation
  - `routers/billing.py` - Stripe integration
  - `database.py` - Supabase client
  - `routers/webhooks.py` - Stripe webhooks
- [x] Implement endpoints:
  - `GET /usage/quota` - Current usage
  - `POST /usage/` - Record events
  - `GET /auth/me` - User info
  - `POST /billing/checkout` - Create checkout session
  - `GET /billing/portal` - Billing portal URL
  - `POST /webhooks/stripe` - Handle subscription events
- [ ] Deploy API (Railway or Vercel) (user action required)

### 2.4 CLI Authentication
- [x] Add `codeshift login` command
- [x] Add `codeshift logout` command
- [x] Update `codeshift status` to show quota
- [x] Add quota check before migrations
- [x] Add usage logging after migrations
- [x] Support offline mode (allow tier1 without auth)

---

## Phase 3: Beta Launch (50+ Testers)

### 3.1 Preparation
- [ ] Make repository public
- [ ] Set up GitHub Discussions
- [ ] Create GitHub Release v0.2.0-beta
- [ ] Verify `pip install codeshift` works

### 3.2 Beta Launch Sequence
- [ ] Week 1: Soft launch with close colleagues (5-10)
- [ ] Week 2: TestPyPI release, test installation
- [ ] Week 3: Post on Reddit r/Python, Twitter, Python Discords
- [ ] Week 4: Hacker News "Show HN" post

### 3.3 Feedback Collection
- [ ] Monitor GitHub Issues
- [ ] Set up optional usage analytics (opt-in)
- [ ] Schedule 5-10 user interviews
- [ ] Create feedback form (Google Form/Typeform)

---

## Phase 4: Paid Tier Launch

### 4.1 Soft Launch ($19 Pro Tier)
- [ ] Enable Stripe checkout in CLI
- [x] Gate LLM migrations behind Pro tier (via server-side API)
- [ ] Add upgrade prompts when quota exceeded
- [ ] Test full flow: signup → payment → API key → migration

### 4.2 Marketing
- [x] Create pricing page on landing page
- [ ] Write announcement blog post
- [ ] Email beta users about paid launch

---

## Phase 5: Growth Features

### 5.1 CI/CD Integration (GitHub Action)
- [ ] Create `codeshift/action` repository
- [ ] Implement weekly scan workflow
- [ ] Add auto-PR creation for migrations
- [ ] Pricing: Free (tier1), $10/mo (developer), $50/mo (team)

### 5.2 Web Dashboard (SaaS Platform)
- [ ] Build React/Next.js frontend
- [ ] GitHub repo connection
- [ ] Migration history & analytics
- [ ] Team accounts and shared settings

### 5.3 IDE Extensions
- [ ] VS Code extension (priority)
- [ ] Show deprecation warnings
- [ ] Quick fix suggestions
- [ ] Pricing: Free (warnings), $9/mo (fixes)

---

## Phase 6: Enterprise & Scale

### 6.1 Enterprise Features
- [ ] Self-hosted deployment option
- [ ] SSO/SAML integration
- [ ] Audit logs
- [ ] Custom knowledge bases
- [ ] SLA guarantees
- [ ] Dedicated support channels

### 6.2 Knowledge Base Marketplace
- [ ] Creator program
- [ ] Revenue sharing (70% creator / 30% platform)
- [ ] Quality review process
- [ ] Marketplace UI

### 6.3 Consulting Services
- [ ] Define service tiers:
  - Migration Audit: $500-2,000
  - Guided Migration: $5,000-20,000
  - Full Migration: $20,000-100,000
- [ ] Create service agreement templates
- [ ] Partner program for agencies

---

## Success Metrics

### Beta Phase (Months 1-3)
| Metric | Target |
|--------|--------|
| GitHub Stars | 500+ |
| Active Beta Users | 50+ |
| Migrations Completed | 500+ |
| GitHub Issues | 30+ |

### Post-Launch (Months 4-12)
| Metric | Target |
|--------|--------|
| Monthly Active Users | 1,000+ |
| Paid Conversions | 2-5% |
| MRR | $5,000+ |
| GitHub Stars | 2,000+ |

---

## Implementation Priority

### Sprint 1: CI/CD + Documentation (COMPLETED)

**CI/CD Pipeline (`.github/workflows/ci.yml`):**
- [x] Run pytest on push/PR
- [x] Run linting (ruff, black --check, mypy)
- [x] Test matrix: Python 3.9, 3.10, 3.11, 3.12
- [x] Upload coverage reports

**Documentation Files:**
- [x] `CONTRIBUTING.md` - How to contribute, dev setup, PR process
- [x] `CODE_OF_CONDUCT.md` - Contributor Covenant
- [x] `.github/ISSUE_TEMPLATE/bug_report.md`
- [x] `.github/ISSUE_TEMPLATE/feature_request.md`
- [x] `.github/PULL_REQUEST_TEMPLATE.md`

**README Updates:**
- [x] Add commercial licensing contact email
- [x] Add badges (CI status, PyPI version, license, Python version)
- [ ] Add demo GIF or screenshot

### Sprint 2: Billing Infrastructure (CODE COMPLETE - Awaiting User Setup)
- [x] Supabase database schema (SQL ready to deploy)
- [ ] Supabase project setup (user action required)
- [ ] Stripe products setup (user action required)
- [x] FastAPI billing API (code complete)
- [x] CLI auth commands (login, logout, whoami, quota, upgrade-plan)
- [x] Server-side LLM migration endpoint
- [x] API client for CLI to call Codeshift API

### Sprint 3: Beta Launch
- Make repo public
- TestPyPI/PyPI release
- Community announcements

### Sprint 4: Paid Tier Launch
- Enable Stripe checkout
- [x] Gate LLM behind Pro tier (implemented via server-side API)
- Pro tier marketing

---

## Files to Create/Modify

### New Files (Phase 2 - COMPLETED):
- [x] `codeshift/api/__init__.py`
- [x] `codeshift/api/main.py` - FastAPI application
- [x] `codeshift/api/auth.py` - API key validation
- [x] `codeshift/api/config.py` - API settings
- [x] `codeshift/api/database.py` - Supabase client
- [x] `codeshift/api/models/__init__.py` - Pydantic models
- [x] `codeshift/api/models/auth.py` - Auth models
- [x] `codeshift/api/models/billing.py` - Billing models
- [x] `codeshift/api/models/usage.py` - Usage models
- [x] `codeshift/api/models/migrate.py` - Migration API models
- [x] `codeshift/api/routers/__init__.py` - Router exports
- [x] `codeshift/api/routers/auth.py` - Auth endpoints
- [x] `codeshift/api/routers/billing.py` - Billing endpoints
- [x] `codeshift/api/routers/usage.py` - Usage endpoints
- [x] `codeshift/api/routers/webhooks.py` - Stripe webhooks
- [x] `codeshift/api/routers/migrate.py` - LLM migration endpoints (server-side Anthropic calls)
- [x] `codeshift/api/migrations/001_initial_schema.sql` - Database schema
- [x] `codeshift/cli/commands/auth.py` - CLI auth commands
- [x] `codeshift/cli/quota.py` - Quota checking utilities
- [x] `codeshift/utils/api_client.py` - API client for CLI to call Codeshift API

### New Files (Phase 1 - COMPLETED):
- [x] `.github/workflows/ci.yml` (test pipeline)
- [x] `CONTRIBUTING.md`
- [x] `CODE_OF_CONDUCT.md`
- [x] `.github/ISSUE_TEMPLATE/bug_report.md`
- [x] `.github/ISSUE_TEMPLATE/feature_request.md`
- [x] `.github/PULL_REQUEST_TEMPLATE.md`

### Modified Files (Phase 2 - COMPLETED):
- [x] `codeshift/cli/main.py` - Add auth commands
- [x] `codeshift/cli/commands/upgrade.py` - Add quota check
- [x] `codeshift/cli/commands/apply.py` - Add usage recording
- [x] `pyproject.toml` - Add new dependencies (supabase, stripe, fastapi)
- [x] `codeshift/migrator/llm_migrator.py` - Refactored to use Codeshift API instead of direct Anthropic calls

### Pending:
- [x] `README.md` - Add commercial contact email
- [x] `landing-page/index.html` - Add pricing section

---

## Environment Variables (Production)

```bash
# Supabase
SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_ANON_KEY=eyJ...
SUPABASE_SERVICE_KEY=eyJ...

# Stripe
STRIPE_SECRET_KEY=sk_live_xxxxx
STRIPE_WEBHOOK_SECRET=whsec_xxxxx
STRIPE_PRICE_PRO=price_xxxxx
STRIPE_PRICE_UNLIMITED=price_xxxxx

# App
PYRESOLVE_API_URL=https://api.codeshift.dev
ANTHROPIC_API_KEY=sk-ant-xxxxx
```

---

## Notes

- This plan will be updated as tasks are completed
- Each phase has dependencies - complete in order
- Focus on billing infrastructure first - it's the foundation for monetization
- Beta feedback will influence priorities for later phases
