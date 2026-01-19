# PyResolve

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

# Analyze and propose changes for a specific library
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
   - **Tier 1**: Deterministic AST transforms for known libraries (pydantic, fastapi, sqlalchemy, pandas, requests)
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

## License

MIT License - see [LICENSE](LICENSE) for details.
