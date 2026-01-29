# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Codeshift is an AI-powered CLI tool that migrates Python code when dependencies are upgraded. Unlike tools that just bump versions, Codeshift rewrites code to be compatible with new library APIs using a tiered approach:

- **Tier 1**: Deterministic libcst AST transforms (Pydantic, FastAPI, SQLAlchemy, Pandas, Requests)
- **Tier 2**: Knowledge base guided LLM migration
- **Tier 3**: Pure LLM fallback for unknown patterns

## Common Commands

```bash
# Install in development mode
pip install -e ".[dev]"

# Run all tests
pytest

# Run specific test file
pytest tests/test_pydantic_transforms.py

# Run specific test
pytest tests/test_pydantic_transforms.py::test_dict_to_model_dump

# Run tests with coverage
pytest --cov=codeshift --cov-report=term-missing

# Lint
ruff check .
black --check .
mypy codeshift --ignore-missing-imports

# Format code
black .

# Run the CLI
codeshift --help
codeshift scan
codeshift upgrade pydantic --target 2.5.0
```

## Architecture

### Core Data Flow

```
scan → DependencyParser + CodeScanner
         ↓
upgrade → KnowledgeGenerator → MigrationEngine
                                  ├→ Tier 1: AST Transforms (codeshift/migrator/transforms/)
                                  ├→ Tier 2: KB + LLM (knowledge/ + llm_migrator.py)
                                  └→ Tier 3: Pure LLM
         ↓
diff → Load state from .codeshift/, show changes
         ↓
apply → Write to disk, record usage
```

### Key Modules

| Directory | Purpose |
|-----------|---------|
| `codeshift/cli/` | Click commands and quota management |
| `codeshift/scanner/` | libcst-based import/usage detection |
| `codeshift/migrator/` | Migration engine and AST transformers |
| `codeshift/migrator/transforms/` | Library-specific transformers (pydantic_v1_to_v2.py, etc.) |
| `codeshift/knowledge/` | Knowledge acquisition pipeline (fetch from GitHub, LLM parsing) |
| `codeshift/knowledge_base/` | Static YAML definitions in `libraries/` |
| `codeshift/analyzer/` | Risk assessment |
| `codeshift/validator/` | Syntax checking |

### Key Data Models

- **ImportInfo/UsageInfo** (scanner/code_scanner.py): Tracks imports and symbol usage
- **BreakingChange** (knowledge/models.py): Represents API changes with confidence levels
- **TransformResult** (migrator/ast_transforms.py): Result of applying transforms
- **RiskAssessment** (analyzer/risk_assessor.py): Migration safety evaluation

## Adding New Library Support

1. Create YAML in `codeshift/knowledge_base/libraries/<library>.yaml`
2. Add transformer in `codeshift/migrator/transforms/<library>_transformer.py`
3. Register in `codeshift/migrator/engine.py` `_get_transform_func()`
4. Add tests in `tests/test_<library>_transforms.py`

## Environment Variables

```bash
ANTHROPIC_API_KEY=sk-ant-...  # Required for LLM features
GITHUB_TOKEN=ghp_...          # Optional, for higher GitHub rate limits
```

## Coding Standards

- Black (line-length: 100)
- Ruff for linting
- Mypy strict mode (disallow_untyped_defs)
- Conventional commits: `feat:`, `fix:`, `docs:`, `test:`, `refactor:`, `chore:`

## Master Plan Task Management

The project roadmap is tracked in `docs/MASTER_PLAN.md` with checkbox items. When completing tasks:

1. Edit `docs/MASTER_PLAN.md`
2. Change `- [ ]` to `- [x]` for completed items
3. Add completion notes if relevant
4. Commit with message: `chore: mark <task description> as done in master plan`

Example:
```markdown
# Before
- [ ] Create demo video/GIF for README

# After
- [x] Create demo video/GIF for README
```
