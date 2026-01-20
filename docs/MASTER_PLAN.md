# PyResolve Master Plan

This document consolidates all goals from `docs/GO_TO_MARKET.md`, `docs/MONETIZATION.md`, and `docs/BILLING_INFRASTRUCTURE.md` into an actionable implementation plan.

---

## Current State Summary

**What Exists:**
- Core migration engine (AST transforms + LLM fallback)
- CLI with 7 commands: `scan`, `upgrade`, `upgrade-all`, `diff`, `apply`, `libraries`, `status`
- 5 Tier 1 libraries: Pydantic, FastAPI, SQLAlchemy, Pandas, Requests
- Knowledge base system that fetches from GitHub
- Tests (4 files, ~860 lines)
- Landing page with GitHub Pages deployment
- Elastic License 2.0

**What's Missing:**
- Authentication (no user accounts)
- Billing (no payments)
- CI/CD for tests
- Documentation files (CONTRIBUTING, CODE_OF_CONDUCT, templates)
- Public release to PyPI

---

## Phase 1: Pre-Launch Foundation

### 1.1 Legal & Licensing
- [x] Add LICENSE file (Elastic License 2.0)
- [x] Update pyproject.toml with correct license
- [x] Update README with license explanation
- [x] Add contact email for commercial licensing in README

### 1.2 Technical Readiness
- [x] Set up CI/CD pipeline (GitHub Actions)
  - [x] Run tests on PRs
  - [x] Run linting (ruff, black, mypy)
  - [x] Test on Python 3.9, 3.10, 3.11, 3.12
- [ ] Increase test coverage (target >70%)
- [ ] Create stable release v0.2.0-beta
- [ ] Publish to TestPyPI first
- [ ] Publish to PyPI

### 1.3 Documentation
- [x] Add CONTRIBUTING.md
- [x] Add CODE_OF_CONDUCT.md
- [x] Create GitHub issue templates (bug, feature request)
- [x] Create PR template
- [ ] Write "Getting Started" tutorial
- [ ] Create demo video/GIF for README

---

## Phase 2: Billing Infrastructure (Supabase + Stripe)

### 2.1 Supabase Setup
- [ ] Create Supabase project "pyresolve"
- [ ] Run database schema SQL:
  - `profiles` table (extends Supabase auth)
  - `api_keys` table with hashing
  - `usage_events` table
  - `monthly_usage` view
  - Helper functions: `create_api_key`, `validate_api_key`, `get_current_usage`
  - Row Level Security policies
- [ ] Note project URL and keys

### 2.2 Stripe Setup
- [ ] Create Stripe account
- [ ] Create products and prices:
  - PyResolve Pro: $19/month
  - PyResolve Unlimited: $49/month
- [ ] Configure webhook endpoint

### 2.3 FastAPI Billing API
- [ ] Create `pyresolve/api/` directory structure:
  - `main.py` - FastAPI app
  - `auth.py` - API key validation
  - `billing.py` - Stripe integration
  - `database.py` - Supabase client
  - `webhooks.py` - Stripe webhooks
- [ ] Implement endpoints:
  - `GET /quota` - Current usage
  - `POST /usage` - Record events
  - `GET /me` - User info
  - `POST /billing/checkout` - Create checkout session
  - `GET /billing/portal` - Billing portal URL
  - `POST /webhooks/stripe` - Handle subscription events
- [ ] Deploy API (Railway or Vercel)

### 2.4 CLI Authentication
- [ ] Add `pyresolve login` command
- [ ] Add `pyresolve logout` command
- [ ] Update `pyresolve status` to show quota
- [ ] Add quota check before migrations
- [ ] Add usage logging after migrations
- [ ] Support offline mode (allow tier1 without auth)

---

## Phase 3: Beta Launch (50+ Testers)

### 3.1 Preparation
- [ ] Make repository public
- [ ] Set up GitHub Discussions
- [ ] Create GitHub Release v0.2.0-beta
- [ ] Verify `pip install pyresolve` works

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
- [ ] Gate LLM migrations behind Pro tier
- [ ] Add upgrade prompts when quota exceeded
- [ ] Test full flow: signup → payment → API key → migration

### 4.2 Marketing
- [ ] Create pricing page on landing page
- [ ] Write announcement blog post
- [ ] Email beta users about paid launch

---

## Phase 5: Growth Features

### 5.1 CI/CD Integration (GitHub Action)
- [ ] Create `pyresolve/action` repository
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
- [ ] Add badges (CI status, PyPI version, license)
- [ ] Add demo GIF or screenshot

### Sprint 2: Billing Infrastructure
- Supabase project + database schema
- Stripe products setup
- FastAPI billing API
- CLI auth commands

### Sprint 3: Beta Launch
- Make repo public
- TestPyPI/PyPI release
- Community announcements

### Sprint 4: Paid Tier Launch
- Enable Stripe checkout
- Gate LLM behind Pro tier
- Pro tier marketing

---

## Files to Create/Modify

### New Files:
- `pyresolve/api/__init__.py`
- `pyresolve/api/main.py`
- `pyresolve/api/auth.py`
- `pyresolve/api/billing.py`
- `pyresolve/api/database.py`
- `pyresolve/api/webhooks.py`
- `pyresolve/cli/auth.py` (login/logout/status)
- `.github/workflows/ci.yml` (test pipeline)
- `CONTRIBUTING.md`
- `CODE_OF_CONDUCT.md`
- `.github/ISSUE_TEMPLATE/bug_report.md`
- `.github/ISSUE_TEMPLATE/feature_request.md`
- `.github/PULL_REQUEST_TEMPLATE.md`

### Modify:
- `pyresolve/cli/main.py` - Add auth commands
- `pyresolve/cli/commands/upgrade.py` - Add quota check
- `pyproject.toml` - Add new dependencies (supabase, stripe, fastapi)
- `README.md` - Add commercial contact email
- `landing-page/index.html` - Add pricing section

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
PYRESOLVE_API_URL=https://api.pyresolve.dev
ANTHROPIC_API_KEY=sk-ant-xxxxx
```

---

## Notes

- This plan will be updated as tasks are completed
- Each phase has dependencies - complete in order
- Focus on billing infrastructure first - it's the foundation for monetization
- Beta feedback will influence priorities for later phases
