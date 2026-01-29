# Getting Started with Codeshift

This guide will help you get up and running with Codeshift in minutes.

## Installation

Install Codeshift using pip:

```bash
pip install codeshift
```

Verify the installation:

```bash
codeshift --help
```

## Prerequisites

### API Key (Optional but Recommended)

For LLM-powered features (auto-generated knowledge bases, complex migrations), you'll need an Anthropic API key:

```bash
export ANTHROPIC_API_KEY="your-api-key"
```

Without an API key, Codeshift will still work for Tier 1 libraries (Pydantic, FastAPI, SQLAlchemy, Pandas, Requests) using deterministic AST transforms.

### GitHub Token (Optional)

For fetching changelogs from private repositories or avoiding rate limits:

```bash
export GITHUB_TOKEN="your-github-token"
```

## Basic Usage

### Step 1: Scan Your Project

First, scan your project to see what dependencies could be upgraded:

```bash
cd your-project
codeshift scan
```

This will show you:
- All dependencies and their current versions
- Available upgrades
- Which tier of migration support is available

Example output:

```
Found 8 dependencies

Outdated Dependencies (2)
┏━━━━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━┳━━━━━━━┳━━━━━━━━━━┓
┃ Package    ┃ Current ┃ Latest ┃ Type  ┃   Tier   ┃
┡━━━━━━━━━━━━╇━━━━━━━━━╇━━━━━━━━╇━━━━━━━╇━━━━━━━━━━┩
│ pydantic   │   1.10  │  2.5.0 │ Major │  Tier 1  │
│ httpx      │   0.23  │ 0.27.0 │ Minor │ Tier 2/3 │
└────────────┴─────────┴────────┴───────┴──────────┘
```

### Step 2: Analyze a Migration

Choose a library to upgrade and analyze what changes would be needed:

```bash
codeshift upgrade pydantic --target 2.5.0
```

Codeshift will:
1. Fetch the knowledge base (or generate it from changelogs)
2. Scan your code for usage of the library
3. Identify all breaking changes that affect your code
4. Propose fixes for each issue

### Step 3: Review the Changes

View the proposed changes with the diff command:

```bash
codeshift diff
```

This shows a detailed diff with explanations:

```diff
--- src/models/user.py (original)
+++ src/models/user.py (migrated)
@@ -1,15 +1,15 @@
-from pydantic import BaseModel, validator
+from pydantic import BaseModel, field_validator, ConfigDict

 class User(BaseModel):
     name: str
     email: str

-    class Config:
-        orm_mode = True
+    model_config = ConfigDict(from_attributes=True)

-    @validator('email')
+    @field_validator('email')
+    @classmethod
     def validate_email(cls, v):
         if '@' not in v:
             raise ValueError('Invalid email')
         return v
```

### Step 4: Apply the Changes

Once you're happy with the proposed changes, apply them:

```bash
codeshift apply
```

Use `--backup` to create backup files:

```bash
codeshift apply --backup
```

### Step 5: Run Your Tests

After applying changes, run your test suite to verify everything works:

```bash
pytest
```

## Upgrade All Dependencies

To scan and upgrade all outdated dependencies at once:

```bash
codeshift upgrade-all
```

This will:
1. Identify all outdated dependencies
2. Prioritize by tier (Tier 1 first, then Tier 2/3)
3. Migrate each library sequentially
4. Show a summary of all changes

## Advanced Options

### Dry Run Mode

Preview changes without saving state:

```bash
codeshift upgrade pydantic --target 2.5.0 --dry-run
```

### Fetch Detailed Breaking Changes

Get detailed breaking change analysis during scan:

```bash
codeshift scan --fetch-changes
```

### JSON Output

Get machine-readable output for CI integration:

```bash
codeshift scan --json-output
```

### Custom Paths

Analyze a specific directory:

```bash
codeshift scan --path ./src
codeshift upgrade pydantic --target 2.5.0 --path ./src
```

## Configuration

Create a `pyproject.toml` configuration:

```toml
[tool.codeshift]
# Paths to exclude from scanning
exclude = ["tests/*", "migrations/*", ".venv/*"]

# Enable LLM for complex migrations (default: true)
use_llm = true

# Cache directory for knowledge bases
# cache_dir = ".codeshift"
```

## Troubleshooting

### "No changes detected"

This usually means:
- The library is already on the target version
- No breaking changes affect your code
- The library isn't used in the scanned path

### "Knowledge base not found"

For non-Tier 1 libraries, you need an `ANTHROPIC_API_KEY` to generate the knowledge base from changelogs.

### Rate Limiting

If you hit GitHub rate limits, set a `GITHUB_TOKEN` environment variable.

## Next Steps

- Check the [Supported Libraries](../README.md#supported-libraries) for full migration support details
- Read about [How It Works](../README.md#how-it-works) for the technical details
- See [CONTRIBUTING.md](../CONTRIBUTING.md) to contribute new library support
