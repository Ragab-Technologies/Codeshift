# PyResolve

[![CI](https://github.com/youssefragab/PyResolve/actions/workflows/ci.yml/badge.svg)](https://github.com/youssefragab/PyResolve/actions/workflows/ci.yml)
[![PyPI version](https://badge.fury.io/py/pyresolve.svg)](https://pypi.org/project/pyresolve/)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**Don't just flag the update. Fix the break.**

PyResolve is an AI-powered CLI tool that migrates Python code to handle breaking dependency changes. Unlike Dependabot/Renovate which just bump versions, PyResolve actually rewrites code to be compatible with new library versions.

## Features

- **Auto-generated knowledge bases** - Fetches changelogs and migration guides from GitHub, parses them with LLM to detect breaking changes
- **Tiered migration approach** - Deterministic AST transforms for known patterns, KB-guided LLM for medium confidence, pure LLM fallback for complex cases
- **Confidence-based change detection** - Shows HIGH/MEDIUM/LOW confidence breaking changes before migration
- **Local test execution** to validate changes before applying
- **Beautiful diff output** with explanations for each change

## Supported Libraries

### Tier 1 Libraries (Deterministic AST Transforms)

| Library | Migration Path | Status |
|---------|---------------|--------|
| Pydantic | v1 → v2 | ✅ Full support |
| FastAPI | 0.x → 0.100+ | ✅ Supported |
| SQLAlchemy | 1.4 → 2.0 | ✅ Supported |
| Pandas | 1.x → 2.x | ✅ Supported |
| Requests | Various | ✅ Supported |
| Django | 3.x → 4.x/5.x | ✅ Supported |
| Flask | 1.x → 2.x/3.x | ✅ Supported |
| NumPy | 1.x → 2.x | ✅ Supported |
| attrs | attr → attrs | ✅ Supported |
| Celery | 4.x → 5.x | ✅ Supported |
| Click | 7.x → 8.x | ✅ Supported |
| aiohttp | 2.x → 3.x | ✅ Supported |
| httpx | 0.x → 0.24+ | ✅ Supported |
| Marshmallow | 2.x → 3.x | ✅ Supported |
| pytest | 6.x → 7.x/8.x | ✅ Supported |

### Any Library (Auto-Generated Knowledge Base)

PyResolve can migrate **any Python library** by automatically fetching changelogs from GitHub and detecting breaking changes. For libraries not in Tier 1, it uses KB-guided or pure LLM migration.

## Installation

```bash
pip install pyresolve
```

## Quick Start

```bash
# Scan your project for all possible migrations
pyresolve scan

# Scan with detailed breaking change analysis
pyresolve scan --fetch-changes

# Upgrade all outdated packages at once
pyresolve upgrade-all

# Or analyze and propose changes for a specific library
pyresolve upgrade pydantic --target 2.5.0

# View detailed diff of proposed changes
pyresolve diff

# Apply changes to your files
pyresolve apply
```

### Example Output

```bash
$ pyresolve upgrade pydantic --target 2.5.0

╭──────────────────────── PyResolve Migration ─────────────────────────╮
│ Upgrading Pydantic to version 2.5.0                                  │
│ Migration guide: https://docs.pydantic.dev/latest/migration/         │
╰──────────────────────────────────────────────────────────────────────╯

Fetching knowledge sources...
   ✓ GitHub: CHANGELOG.md
   ✓ GitHub: docs/migration.md

Breaking changes detected:

   HIGH CONFIDENCE:
   ├── .dict() → .model_dump()
   ├── @validator → @field_validator
   └── class Config → model_config = ConfigDict()

   MEDIUM CONFIDENCE:
   ├── .json() → .model_dump_json()
   └── parse_obj() → model_validate()

Scanning for library usage...
Found 12 imports from pydantic
Found 45 usages of pydantic symbols

┏━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━┓
┃ File               ┃ Changes ┃ Status ┃
┡━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━╇━━━━━━━━┩
│ src/models/user.py │       5 │ Ready  │
│ src/api/schemas.py │       3 │ Ready  │
└────────────────────┴─────────┴────────┘

Total: 8 changes across 2 files
```

## Usage

### Scan Command

Scan your entire project for possible dependency migrations:

```bash
pyresolve scan

# Options:
#   --path, -p         Path to scan (default: current directory)
#   --fetch-changes    Fetch changelogs and detect breaking changes (slower)
#   --major-only       Only show major version upgrades
#   --json-output      Output results as JSON
#   --verbose, -v      Show detailed output
```

Example output:

```bash
$ pyresolve scan

Found 13 dependencies

Outdated Dependencies (5)
┏━━━━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━┳━━━━━━━┳━━━━━━━━━━┓
┃ Package    ┃ Current ┃ Latest ┃ Type  ┃   Tier   ┃
┡━━━━━━━━━━━━╇━━━━━━━━━╇━━━━━━━━╇━━━━━━━╇━━━━━━━━━━┩
│ pydantic   │     1.0 │  2.5.0 │ Major │  Tier 1  │
│ rich       │    13.0 │ 14.0.0 │ Major │ Tier 2/3 │
└────────────┴─────────┴────────┴───────┴──────────┘

Suggested Migrations (2)
  pydantic 1.0 → 2.5.0 (Tier 1 - deterministic)
  rich 13.0 → 14.0.0 (Tier 2/3 - LLM-assisted)

Quick commands:
  pyresolve upgrade pydantic --target 2.5.0
  pyresolve upgrade rich --target 14.0.0
```

### Upgrade Command

Analyze your codebase and propose changes for a library upgrade:

```bash
pyresolve upgrade <library> --target <version>

# Options:
#   --target, -t    Target version to upgrade to
#   --path, -p      Path to analyze (default: current directory)
#   --dry-run       Show what would be changed without saving state
```

### Diff Command

View the detailed diff of proposed changes:

```bash
pyresolve diff

# Options:
#   --file, -f      Show diff for specific file only
#   --no-color      Disable colored output
```

### Apply Command

Apply the proposed changes to your files:

```bash
pyresolve apply

# Options:
#   --backup        Create backup files before applying changes
#   --file, -f      Apply changes to specific file only
```

### Upgrade-All Command

Upgrade all outdated packages to their latest versions in one go:

```bash
pyresolve upgrade-all

# Options:
#   --all, -a       Include all outdated packages (not just Tier 1)
#   --path, -p      Path to analyze (default: current directory)
#   --dry-run       Show what would be changed without saving state
```

### Libraries Command

List all supported libraries and their migration paths:

```bash
pyresolve libraries
```

### Status Command

Show current migration status, pending changes, and quota information:

```bash
pyresolve status
```

## How It Works

```text
┌─────────────────────────────────────────────────────────────────────┐
│                     Knowledge Acquisition Pipeline                   │
│  ┌─────────────┐   ┌──────────────────┐   ┌─────────────────────┐  │
│  │ Local Cache │──▶│ On-Demand Gen    │──▶│ LLM Parser          │  │
│  │ (instant)   │   │ (fetches sources)│   │ (breaking changes)  │  │
│  └─────────────┘   └──────────────────┘   └─────────────────────┘  │
│                            │                                        │
│            ┌───────────────┴───────────────┐                       │
│            │  Source Fetchers              │                       │
│            │  ├── GitHub (CHANGELOG.md)    │                       │
│            │  ├── Docs (migration guides)  │                       │
│            │  └── Release notes            │                       │
│            └───────────────────────────────┘                       │
└─────────────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    Migration Engine (Tiered)                        │
│  Tier 1: AST Transforms  │  Tier 2: KB-Guided  │  Tier 3: LLM      │
│  (deterministic)         │  (context + LLM)    │  (fallback)       │
└─────────────────────────────────────────────────────────────────────┘
```

1. **Fetch Knowledge**: Discovers and fetches changelogs, migration guides from GitHub/PyPI
2. **Parse Changes**: Uses LLM to extract breaking changes with confidence levels (HIGH/MEDIUM/LOW)
3. **Scan Codebase**: Finds imports and usage of the target library
4. **Tiered Migration**:
   - **Tier 1**: Deterministic AST transforms for 15 supported libraries (Pydantic, FastAPI, SQLAlchemy, Django, Flask, NumPy, Pandas, Requests, attrs, Celery, Click, aiohttp, httpx, Marshmallow, pytest)
   - **Tier 2**: Knowledge base guided migration with LLM assistance
   - **Tier 3**: Pure LLM migration for unknown patterns
5. **Validate**: Runs syntax checks and optionally your test suite
6. **Report**: Shows a detailed diff with explanations for each change

## Pydantic v1 → v2 Transforms

PyResolve handles the following Pydantic migrations automatically:

- `Config` class → `model_config = ConfigDict(...)`
- `@validator` → `@field_validator` with `@classmethod`
- `@root_validator` → `@model_validator`
- `.dict()` → `.model_dump()`
- `.json()` → `.model_dump_json()`
- `.schema()` → `.model_json_schema()`
- `.parse_obj()` → `.model_validate()`
- `orm_mode = True` → `from_attributes = True`
- `Field(regex=...)` → `Field(pattern=...)`

## Configuration

PyResolve can be configured via `pyproject.toml`:

```toml
[tool.pyresolve]
# Path patterns to exclude from scanning (defaults: .pyresolve/*, tests/*, .venv/*, venv/*)
exclude = ["tests/*", "migrations/*"]

# Enable/disable LLM fallback
use_llm = true

# Anthropic API key (can also use ANTHROPIC_API_KEY env var)
# anthropic_api_key = "sk-..."
```

## Pricing

PyResolve uses a tiered pricing model:

| Tier | Price | Features |
|------|-------|----------|
| **Free** | $0/month | Tier 1 deterministic transforms (15 libraries including Pydantic, Django, Flask, SQLAlchemy, and more) |
| **Pro** | $19/month | Tier 2 KB-guided LLM migrations for any library |
| **Unlimited** | $49/month | Tier 3 pure LLM migrations + priority support |

**How it works:**
- **Tier 1 (Free)**: Runs entirely locally using deterministic AST transforms. No account required.
- **Tier 2/3 (Paid)**: LLM-powered migrations are processed through the PyResolve API to ensure quality and manage costs.

```bash
# Login to access Pro/Unlimited features
pyresolve login

# Check your current plan and usage
pyresolve quota
```

## License

This software is licensed under the [MIT License](LICENSE).

You are free to use, modify, and distribute this software. The CLI tool and all transforms are fully open source.
