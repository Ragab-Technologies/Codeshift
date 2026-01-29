# Contributing to Codeshift

Thank you for your interest in contributing to Codeshift! This document provides guidelines and instructions for contributing.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Making Changes](#making-changes)
- [Pull Request Process](#pull-request-process)
- [Coding Standards](#coding-standards)
- [Testing](#testing)
- [Adding New Library Support](#adding-new-library-support)

## Code of Conduct

Please read and follow our [Code of Conduct](CODE_OF_CONDUCT.md) to maintain a welcoming and inclusive community.

## Getting Started

1. **Fork the repository** on GitHub
2. **Clone your fork** locally:
   ```bash
   git clone https://github.com/YOUR_USERNAME/Codeshift.git
   cd Codeshift
   ```
3. **Add the upstream remote**:
   ```bash
   git remote add upstream https://github.com/youssefragab/Codeshift.git
   ```

## Development Setup

### Prerequisites

- Python 3.9 or higher
- Git

### Installation

1. Create a virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

2. Install the package in development mode with dev dependencies:
   ```bash
   pip install -e ".[dev]"
   ```

3. Verify the installation:
   ```bash
   codeshift --help
   ```

### Environment Variables

For full functionality, set the following environment variables:

```bash
export ANTHROPIC_API_KEY="your-api-key"  # Required for LLM features
export GITHUB_TOKEN="your-github-token"  # Optional, for higher rate limits
```

## Making Changes

1. **Create a new branch** from `main`:
   ```bash
   git checkout main
   git pull upstream main
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes** following our [coding standards](#coding-standards)

3. **Write or update tests** for your changes

4. **Run the test suite**:
   ```bash
   pytest
   ```

5. **Run linting**:
   ```bash
   ruff check .
   black --check .
   mypy codeshift --ignore-missing-imports
   ```

6. **Commit your changes** with a descriptive message:
   ```bash
   git commit -m "feat: add support for new library transformation"
   ```

## Pull Request Process

1. **Push your branch** to your fork:
   ```bash
   git push origin feature/your-feature-name
   ```

2. **Open a Pull Request** against `main` on the upstream repository

3. **Fill out the PR template** completely

4. **Wait for CI checks** to pass

5. **Address review feedback** if any

### PR Requirements

- All CI checks must pass
- Code must be properly formatted (black) and linted (ruff)
- New features should include tests
- Documentation should be updated if needed

## Coding Standards

### Style Guide

We use the following tools to maintain code quality:

- **black** for code formatting (line length: 100)
- **ruff** for linting
- **mypy** for type checking

### Commit Messages

We follow [Conventional Commits](https://www.conventionalcommits.org/):

- `feat:` - New features
- `fix:` - Bug fixes
- `docs:` - Documentation changes
- `test:` - Adding or updating tests
- `refactor:` - Code refactoring
- `chore:` - Maintenance tasks

Examples:
```
feat: add SQLAlchemy 2.0 migration transforms
fix: handle nested class Config in Pydantic models
docs: update README with new scan command options
```

### Code Organization

```
codeshift/
├── cli/            # CLI commands and argument parsing
├── scanner/        # Code scanning and import detection
├── analyzer/       # Risk assessment and change detection
├── migrator/       # AST transforms and LLM migration
├── validator/      # Syntax checking and test running
├── knowledge_base/ # Library migration knowledge
└── utils/          # Shared utilities (LLM client, cache)
```

## Testing

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=codeshift --cov-report=term-missing

# Run specific test file
pytest tests/test_pydantic_transforms.py

# Run specific test
pytest tests/test_pydantic_transforms.py::test_dict_to_model_dump
```

### Writing Tests

- Place tests in the `tests/` directory
- Use descriptive test names: `test_<feature>_<scenario>`
- Include both positive and negative test cases
- Use fixtures for common test data (see `tests/fixtures/`)

## Adding New Library Support

To add support for a new library migration:

1. **Create a knowledge base file** in `codeshift/knowledge_base/libraries/`:
   ```yaml
   # codeshift/knowledge_base/libraries/newlib.yaml
   library: newlib
   from_version: "1.0"
   to_version: "2.0"
   migration_guide: "https://..."

   transforms:
     - name: old_function_to_new
       type: function_rename
       old: old_function
       new: new_function
       confidence: high
   ```

2. **Add AST transforms** in `codeshift/migrator/ast_transforms.py` if deterministic transforms are possible

3. **Add tests** in `tests/test_<library>_transforms.py`

4. **Update documentation** to list the new library

## Questions?

If you have questions about contributing, feel free to:

- Open a [Discussion](https://github.com/youssefragab/Codeshift/discussions)
- Open an [Issue](https://github.com/youssefragab/Codeshift/issues)

Thank you for contributing to Codeshift!
