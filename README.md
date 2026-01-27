# Codeshift

[![CI](https://github.com/Ragab-Technologies/Codeshift/actions/workflows/ci.yml/badge.svg)](https://github.com/Ragab-Technologies/Codeshift/actions/workflows/ci.yml)
[![PyPI version](https://badge.fury.io/py/codeshift.svg)](https://pypi.org/project/codeshift/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**Don't just flag the update. Fix the break.**

Codeshift is an AI-powered CLI tool that migrates Python code when dependencies are upgraded. Unlike Dependabot or Renovate which only bump version numbers, Codeshift rewrites your code to be compatible with new library APIs.

## Why Codeshift?

Upgrading a dependency often means updating dozens of call sites to match a new API. Codeshift automates that:

- **Scans** your project for outdated dependencies
- **Detects** breaking changes from changelogs and migration guides
- **Rewrites** your code using deterministic AST transforms or LLM assistance
- **Shows** a detailed diff with explanations before touching any file

## Features

- **Deterministic AST transforms** for 15 popular libraries (no LLM required)
- **Auto-generated knowledge bases** - fetches changelogs and migration guides from GitHub, parses them with an LLM to detect breaking changes
- **Tiered migration engine** - deterministic transforms first, KB-guided LLM second, pure LLM fallback last
- **Confidence-based change detection** - shows HIGH/MEDIUM/LOW confidence breaking changes before migration
- **Beautiful diff output** with per-change explanations
- **Backup and restore** so you can safely revert
- **Batch upgrades** - migrate all outdated dependencies in one command

## Supported Libraries

### Tier 1 (Deterministic AST Transforms - Free, No LLM Required)

| Library | Migration Path | Status |
|---------|---------------|--------|
| Pydantic | v1 → v2 | Supported |
| FastAPI | 0.x → 0.100+ | Supported |
| SQLAlchemy | 1.4 → 2.0 | Supported |
| Pandas | 1.x → 2.x | Supported |
| Requests | Various | Supported |
| Django | 3.x → 4.x/5.x | Supported |
| Flask | 1.x → 2.x/3.x | Supported |
| NumPy | 1.x → 2.x | Supported |
| attrs | attr → attrs | Supported |
| Celery | 4.x → 5.x | Supported |
| Click | 7.x → 8.x | Supported |
| aiohttp | 2.x → 3.x | Supported |
| httpx | 0.x → 0.24+ | Supported |
| Marshmallow | 2.x → 3.x | Supported |
| pytest | 6.x → 7.x/8.x | Supported |

### Any Library (Auto-Generated Knowledge Base)

Codeshift can migrate **any Python library** by automatically fetching changelogs from GitHub and detecting breaking changes. For libraries not in Tier 1, it uses KB-guided or pure LLM migration.

## Installation

```bash
pip install codeshift
```

For development:

```bash
pip install codeshift[dev]
```

Verify the installation:

```bash
codeshift --help
```

## Quick Start

```bash
# 1. Scan your project for outdated dependencies
codeshift scan

# 2. Upgrade a specific library
codeshift upgrade pydantic --target 2.5.0

# 3. Review the proposed changes
codeshift diff

# 4. Apply the changes
codeshift apply

# 5. Run your tests to verify
pytest
```

Or upgrade everything at once:

```bash
codeshift upgrade-all
```

### Example Output

```
$ codeshift upgrade pydantic --target 2.5.0

╭──────────────────────── Codeshift Migration ─────────────────────────╮
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

## Commands

### `codeshift scan`

Scan your project for outdated dependencies and available migrations.

```bash
codeshift scan [OPTIONS]

Options:
  --path, -p PATH       Path to scan (default: current directory)
  --fetch-changes       Fetch changelogs and detect breaking changes
  --major-only          Only show major version upgrades
  --json-output         Output results as JSON
  --verbose, -v         Show detailed output
```

Example:

```
$ codeshift scan

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
  codeshift upgrade pydantic --target 2.5.0
  codeshift upgrade rich --target 14.0.0
```

### `codeshift upgrade`

Analyze your codebase and propose changes for a specific library upgrade.

```bash
codeshift upgrade <library> --target <version> [OPTIONS]

Arguments:
  LIBRARY               Library name to upgrade (required)

Options:
  --target, -t VERSION  Target version to upgrade to (required)
  --path, -p PATH       Path to analyze (default: current directory)
  --file, -f PATH       Analyze a single file instead of the entire project
  --dry-run             Show what would be changed without saving state
  --verbose, -v         Show detailed output
```

### `codeshift upgrade-all`

Upgrade all outdated packages to their latest versions in one go.

```bash
codeshift upgrade-all [OPTIONS]

Options:
  --path, -p PATH       Path to analyze (default: current directory)
  --all                 Include all outdated packages (not just Tier 1)
  --tier1-only          Only upgrade Tier 1 libraries (deterministic transforms)
  --major-only          Only perform major version upgrades
  --include, -i LIB     Only include specific libraries (repeatable)
  --exclude, -e LIB     Exclude specific libraries (repeatable)
  --update-deps         Update dependency files with new versions (default: yes)
  --no-update-deps      Skip updating dependency files
  --dry-run             Show what would be changed without saving state
  --verbose, -v         Show detailed output
```

### `codeshift diff`

View the detailed diff of proposed changes.

```bash
codeshift diff [OPTIONS]

Options:
  --path, -p PATH       Path to the project (default: current directory)
  --file, -f FILE       Show diff for a specific file only
  --no-color            Disable colored output
  --context, -c INT     Number of context lines (default: 3)
  --summary             Show only a summary without the full diff
```

### `codeshift show`

Show the full transformed or original code for a file.

```bash
codeshift show <file_path> [OPTIONS]

Arguments:
  FILE_PATH             File to display (required)

Options:
  --path, -p PATH       Path to the project (default: current directory)
  --original            Show the original code instead of the transformed version
```

### `codeshift apply`

Apply the proposed changes to your files.

```bash
codeshift apply [OPTIONS]

Options:
  --path, -p PATH       Path to the project (default: current directory)
  --file, -f FILE       Apply changes to a specific file only
  --backup              Create .bak backup files before applying changes
  --yes, -y             Skip confirmation prompt
  --validate            Validate syntax after applying (default: yes)
  --no-validate         Skip syntax validation
```

### `codeshift reset`

Cancel the current migration and clear all pending changes.

```bash
codeshift reset [OPTIONS]

Options:
  --path, -p PATH       Path to the project (default: current directory)
  --yes, -y             Skip confirmation prompt
```

### `codeshift restore`

Restore files from a backup created by `apply --backup`.

```bash
codeshift restore <backup_dir> [OPTIONS]

Arguments:
  BACKUP_DIR            Path to backup directory (required)

Options:
  --path, -p PATH       Path to the project (default: current directory)
  --yes, -y             Skip confirmation prompt
```

### `codeshift libraries`

List all supported libraries and their migration paths.

```bash
codeshift libraries
```

### `codeshift status`

Show current migration status, pending changes, and quota info.

```bash
codeshift status [OPTIONS]

Options:
  --path, -p PATH       Path to the project (default: current directory)
```

### Account Commands

```bash
codeshift login              # Login to enable cloud features
codeshift register           # Create a new account
codeshift logout             # Logout and remove credentials
codeshift whoami             # Show current user info
codeshift quota              # Show usage and limits
codeshift upgrade-plan       # View or upgrade your plan
codeshift billing            # Open billing portal
```

## How It Works

```
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

1. **Fetch Knowledge** - discovers and fetches changelogs, migration guides from GitHub/PyPI
2. **Parse Changes** - uses an LLM to extract breaking changes with confidence levels (HIGH/MEDIUM/LOW)
3. **Scan Codebase** - finds imports and usage of the target library using libcst
4. **Tiered Migration**:
   - **Tier 1**: deterministic AST transforms for 15 supported libraries - no LLM needed
   - **Tier 2**: knowledge base guided migration with LLM assistance
   - **Tier 3**: pure LLM migration for unknown patterns
5. **Validate** - runs syntax checks on the transformed code
6. **Report** - shows a detailed diff with explanations for each change

## Pydantic v1 → v2 Example

Codeshift handles the following Pydantic migrations automatically:

| v1 Pattern | v2 Replacement |
|---|---|
| `Config` class | `model_config = ConfigDict(...)` |
| `@validator` | `@field_validator` with `@classmethod` |
| `@root_validator` | `@model_validator` |
| `.dict()` | `.model_dump()` |
| `.json()` | `.model_dump_json()` |
| `.schema()` | `.model_json_schema()` |
| `.parse_obj()` | `.model_validate()` |
| `orm_mode = True` | `from_attributes = True` |
| `Field(regex=...)` | `Field(pattern=...)` |

## Configuration

Codeshift can be configured via `pyproject.toml`:

```toml
[tool.codeshift]
# Path patterns to exclude from scanning
exclude = ["tests/*", "migrations/*"]

# Enable/disable LLM fallback
use_llm = true

# Anthropic API key (can also use ANTHROPIC_API_KEY env var)
# anthropic_api_key = "sk-..."
```

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | For Tier 2/3 | Enables LLM-powered migrations |
| `GITHUB_TOKEN` | No | Higher GitHub API rate limits |

## Pricing

| Tier | Price | What You Get |
|------|-------|--------------|
| **Free** | $0/month | Tier 1 deterministic transforms for all 15 supported libraries. Runs entirely locally. |
| **Pro** | $19/month | Tier 2 KB-guided LLM migrations for any library |
| **Unlimited** | $49/month | Tier 3 pure LLM migrations + priority support |

```bash
# Login to access Pro/Unlimited features
codeshift login

# Check your current plan and usage
codeshift quota
```

## License

This software is licensed under the [MIT License](LICENSE).

You are free to use, modify, and distribute this software. The CLI tool and all transforms are fully open source.
