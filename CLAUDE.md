# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Structure

This is a monorepo containing two Python projects:

| Directory | Description |
|-----------|-------------|
| `codeshift-cli/` | AI-powered CLI tool that migrates Python code when dependencies are upgraded |
| `codeshift-server/` | FastAPI backend for authentication, billing (Stripe), and server-side LLM migrations |

**See the CLAUDE.md in each subdirectory for project-specific commands and architecture details.**

## Quick Reference

### CLI (codeshift-cli/)
```bash
cd codeshift-cli
pip install -e ".[dev]"
pytest
codeshift --help
```

### Server (codeshift-server/)
```bash
cd codeshift-server
pip install -e ".[dev]"
uvicorn codeshift_server.main:app --reload --port 8000
pytest
```

## Cross-Project Context

- **CLI ↔ Server Communication**: CLI authenticates via API key in `X-API-Key` header, calls server for Tier 2/3 LLM migrations, usage tracking, and subscription management
- **Tier System**: free (Tier 1 local transforms) → pro (Tier 2 KB-guided) → unlimited (Tier 3 pure LLM)
- **Shared Tooling**: Both use black (line-length 100), ruff, mypy strict mode, conventional commits

## Coding Standards

Both projects follow:
- Black formatting (line-length: 100)
- Ruff for linting
- Mypy with `disallow_untyped_defs`
- Conventional commits: `feat:`, `fix:`, `docs:`, `test:`, `refactor:`, `chore:`
