# Codeshift GitHub Action

Automate dependency migrations in your CI/CD pipeline with the Codeshift GitHub Action. This action scans your project for outdated dependencies, applies migrations, and creates pull requests with detailed changelogs and risk assessments.

## Features

- **Automated Scanning**: Detects outdated dependencies and available migrations
- **Tiered Migration**: Tier 1 (deterministic AST transforms) works without any API key
- **Risk Assessment**: Evaluates migration safety before applying changes
- **Rich PR Descriptions**: Includes migration tables, risk factors, and recommendations
- **Test Integration**: Optionally runs your test suite after migration
- **Configurable**: Control which libraries to migrate, risk thresholds, and more

## Quick Start

Add this workflow to your repository at `.github/workflows/codeshift.yml`:

```yaml
name: Codeshift Migration

on:
  # Run weekly on Monday at 9 AM UTC
  schedule:
    - cron: '0 9 * * 1'

  # Allow manual triggers
  workflow_dispatch:

permissions:
  contents: write
  pull-requests: write

jobs:
  migrate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Run Codeshift Migration
        uses: Ragab-Technologies/codeshift@v1
        with:
          github-token: ${{ secrets.GITHUB_TOKEN }}
```

## Usage Options

### Option 1: Direct Reference (Recommended)

Reference the action directly from the Codeshift repository:

```yaml
- uses: Ragab-Technologies/codeshift@v1
  with:
    github-token: ${{ secrets.GITHUB_TOKEN }}
```

### Option 2: Nested Action Reference

If you need to reference a specific version or the nested action path:

```yaml
- uses: Ragab-Technologies/codeshift/.github/actions/codeshift-migrate@main
  with:
    github-token: ${{ secrets.GITHUB_TOKEN }}
```

## Inputs

| Input | Description | Required | Default |
|-------|-------------|----------|---------|
| `github-token` | GitHub token for creating PRs | Yes | `${{ github.token }}` |
| `codeshift-api-key` | API key for Tier 2/3 migrations | No | - |
| `libraries` | Comma-separated list of libraries to migrate | No | `""` (all) |
| `tier1-only` | Only run Tier 1 (deterministic) migrations | No | `true` |
| `auto-apply` | Auto-apply if risk is below threshold | No | `true` |
| `create-pr` | Create a pull request | No | `true` |
| `run-tests` | Run tests after migration | No | `true` |
| `test-command` | Command to run tests | No | `pytest` |
| `max-risk-level` | Max risk level for auto-apply (`low`, `medium`, `high`) | No | `medium` |
| `base-branch` | Base branch for the PR | No | `main` |
| `branch-prefix` | Prefix for migration branches | No | `codeshift/migration` |
| `python-version` | Python version to use | No | `3.11` |
| `working-directory` | Working directory for migration | No | `.` |

## Outputs

| Output | Description |
|--------|-------------|
| `pr-url` | URL of the created pull request |
| `pr-number` | Number of the created pull request |
| `migrations-count` | Number of migrations performed |
| `files-changed` | Number of files changed |
| `risk-level` | Overall risk level (`low`, `medium`, `high`, `critical`) |
| `test-passed` | Whether tests passed (`true`/`false`) |
| `json-report` | Path to the JSON report file |

## Examples

### Basic Usage (Tier 1 Only)

Runs deterministic migrations for supported libraries (pydantic, fastapi, sqlalchemy, pandas, requests, etc.) without requiring an API key:

```yaml
name: Weekly Dependency Migration

on:
  schedule:
    - cron: '0 9 * * 1'

permissions:
  contents: write
  pull-requests: write

jobs:
  migrate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - uses: Ragab-Technologies/codeshift@v1
        with:
          github-token: ${{ secrets.GITHUB_TOKEN }}
          tier1-only: 'true'
```

### Migrate Specific Libraries

```yaml
- uses: Ragab-Technologies/codeshift@v1
  with:
    github-token: ${{ secrets.GITHUB_TOKEN }}
    libraries: 'pydantic,fastapi'
```

### With Tier 2/3 Migrations (API Key Required)

For LLM-assisted migrations of libraries without deterministic transforms:

```yaml
- uses: Ragab-Technologies/codeshift@v1
  with:
    github-token: ${{ secrets.GITHUB_TOKEN }}
    codeshift-api-key: ${{ secrets.CODESHIFT_API_KEY }}
    tier1-only: 'false'
```

### Custom Test Command

```yaml
- uses: Ragab-Technologies/codeshift@v1
  with:
    github-token: ${{ secrets.GITHUB_TOKEN }}
    run-tests: 'true'
    test-command: 'pytest tests/ -v --tb=short'
```

### Conservative Risk Settings

Only auto-apply low-risk migrations:

```yaml
- uses: Ragab-Technologies/codeshift@v1
  with:
    github-token: ${{ secrets.GITHUB_TOKEN }}
    max-risk-level: 'low'
```

### Manual Trigger with Inputs

```yaml
name: Codeshift Migration

on:
  workflow_dispatch:
    inputs:
      libraries:
        description: 'Libraries to migrate (comma-separated)'
        required: false
        default: ''
      tier1-only:
        description: 'Tier 1 only'
        type: boolean
        default: true

jobs:
  migrate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - uses: Ragab-Technologies/codeshift@v1
        with:
          github-token: ${{ secrets.GITHUB_TOKEN }}
          libraries: ${{ github.event.inputs.libraries }}
          tier1-only: ${{ github.event.inputs.tier1-only }}
```

### Using Outputs

```yaml
- name: Run Migration
  id: codeshift
  uses: Ragab-Technologies/codeshift@v1
  with:
    github-token: ${{ secrets.GITHUB_TOKEN }}

- name: Summary
  run: |
    echo "Migrations: ${{ steps.codeshift.outputs.migrations-count }}"
    echo "Files changed: ${{ steps.codeshift.outputs.files-changed }}"
    echo "Risk level: ${{ steps.codeshift.outputs.risk-level }}"
    if [ -n "${{ steps.codeshift.outputs.pr-url }}" ]; then
      echo "PR: ${{ steps.codeshift.outputs.pr-url }}"
    fi
```

### With Slack Notification

```yaml
- name: Run Migration
  id: codeshift
  uses: Ragab-Technologies/codeshift@v1
  with:
    github-token: ${{ secrets.GITHUB_TOKEN }}

- name: Notify Slack
  if: steps.codeshift.outputs.pr-url != ''
  uses: slackapi/slack-github-action@v1.24.0
  with:
    payload: |
      {
        "text": "Codeshift created a migration PR: ${{ steps.codeshift.outputs.pr-url }}"
      }
  env:
    SLACK_WEBHOOK_URL: ${{ secrets.SLACK_WEBHOOK_URL }}
```

## Migration Tiers

| Tier | Description | API Key Required |
|------|-------------|------------------|
| **Tier 1** | Deterministic AST transforms for well-known libraries | No |
| **Tier 2** | Knowledge-base guided LLM migration | Yes |
| **Tier 3** | Pure LLM migration for unknown patterns | Yes |

### Tier 1 Supported Libraries

The following libraries have deterministic transforms that work without an API key:

- `pydantic` (v1 to v2)
- `fastapi`
- `sqlalchemy`
- `pandas`
- `requests`
- `numpy`
- `marshmallow`
- `pytest`
- `attrs`
- `django`
- `flask`
- `celery`
- `click`
- `httpx`
- `aiohttp`

## Risk Assessment

The action evaluates migration risk based on:

- **Transform Determinism**: Tier 1 transforms are low risk
- **Change Complexity**: More changes = higher risk
- **File Criticality**: Changes to auth/security/config files increase risk
- **Test Coverage**: Higher coverage = higher confidence

Risk levels:
- **Low**: Safe for auto-apply
- **Medium**: Safe with `is_safe=true` and confidence >= 70%
- **High**: Manual review recommended
- **Critical**: Do not auto-apply

## Pull Request Format

Created PRs include:

1. **Migration Summary Table**: Library versions, file counts, changes
2. **Risk Assessment**: Overall risk, confidence score, factors
3. **Test Results**: Pass/fail status if tests were run
4. **Files Changed**: Collapsible list of modified files
5. **Breaking Changes**: What API changes were addressed

## Troubleshooting

### No migrations found

- Ensure your `requirements.txt` or `pyproject.toml` has pinned versions
- Check that the libraries you want to migrate are actually outdated

### PR not created

- Verify `permissions: contents: write, pull-requests: write` is set
- Check that `GITHUB_TOKEN` has necessary permissions
- Ensure there are actual code changes (not just dependency file updates)

### Tier 2/3 migrations not working

- Set `tier1-only: 'false'`
- Add `codeshift-api-key: ${{ secrets.CODESHIFT_API_KEY }}`
- Ensure you have a valid Codeshift account with API access

## Security

- The action only modifies files in your repository
- API keys are never logged or exposed
- PRs require your normal review process before merging
- Tier 1 migrations run entirely locally with no external API calls
