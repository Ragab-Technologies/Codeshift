# PyResolve

**Don't just flag the update. Fix the break.**

PyResolve is an AI-powered CLI tool that migrates Python code to handle breaking dependency changes. Unlike Dependabot/Renovate which just bump versions, PyResolve actually rewrites code to be compatible with new library versions.

## Features

- **Deterministic AST transforms** using LibCST for known migration patterns
- **LLM fallback** (Anthropic Claude) for complex cases that can't be handled deterministically
- **Local test execution** to validate changes before applying
- **Beautiful diff output** with explanations for each change

## Supported Libraries

| Library | Migration Path | Status |
|---------|---------------|--------|
| Pydantic | v1 → v2 | ✅ Supported |
| FastAPI | Various | 🚧 Coming soon |
| SQLAlchemy | 1.4 → 2.0 | 🚧 Coming soon |
| Pandas | 1.x → 2.x | 🚧 Coming soon |
| Requests | Various | 🚧 Coming soon |

## Installation

```bash
pip install pyresolve
```

## Quick Start

```bash
# Analyze your project and propose changes
pyresolve upgrade pydantic --target 2.5.0

# View detailed diff of proposed changes
pyresolve diff

# Apply changes to your files
pyresolve apply
```

## Usage

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

1. **Scan**: PyResolve scans your codebase to find imports and usage of the target library
2. **Analyze**: Cross-references usage against a knowledge base of breaking changes
3. **Transform**: Applies deterministic AST transforms for known patterns
4. **Fallback**: Uses LLM for complex cases that can't be handled deterministically
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
# Path patterns to exclude from scanning
exclude = ["tests/*", "migrations/*"]

# Enable/disable LLM fallback
use_llm = true

# Anthropic API key (can also use ANTHROPIC_API_KEY env var)
# anthropic_api_key = "sk-..."
```

## Development

```bash
# Clone the repository
git clone https://github.com/youssefragab/PyResolve.git
cd PyResolve

# Install in development mode
pip install -e ".[dev]"

# Run tests
pytest

# Run linting
ruff check .
black --check .
```

## License

MIT License - see [LICENSE](LICENSE) for details.
