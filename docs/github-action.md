# Codeshift GitHub Action

Automate dependency migrations in your CI/CD pipeline. Codeshift scans your Python project for outdated dependencies, rewrites code to match new APIs, and opens a pull request with the changes.

## Quick Start

```yaml
name: Codeshift Migration
on:
  schedule:
    - cron: '0 9 * * 1'  # Every Monday at 9am
  workflow_dispatch:

permissions:
  contents: write
  pull-requests: write

jobs:
  migrate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: Ragab-Technologies/codeshift@v1
        with:
          github-token: ${{ secrets.GITHUB_TOKEN }}
```

## Inputs

| Input | Description | Required | Default |
|-------|-------------|----------|---------|
| `codeshift-api-key` | Codeshift API key for Tier 2/3 migrations. Not required for Tier 1 (deterministic) migrations. | No | |
| `github-token` | GitHub token for creating PRs and branches | Yes | `${{ github.token }}` |
| `libraries` | Comma-separated list of libraries to migrate (e.g., `"pydantic,fastapi"`). Leave empty for all. | No | `''` |
| `auto-apply` | Automatically apply changes if risk is below `max-risk-level` | No | `'true'` |
| `create-pr` | Create a pull request with the changes | No | `'true'` |
| `run-tests` | Run tests after migration | No | `'true'` |
| `test-command` | Command to run tests | No | `'pytest'` |
| `max-risk-level` | Maximum risk level for auto-apply (`low`, `medium`, `high`) | No | `'medium'` |
| `base-branch` | Base branch for the PR | No | `'main'` |
| `branch-prefix` | Prefix for migration branches | No | `'codeshift/migration'` |
| `python-version` | Python version to use | No | `'3.11'` |
| `tier1-only` | Only run Tier 1 (deterministic) migrations — no API key required | No | `'true'` |
| `working-directory` | Working directory for the migration | No | `'.'` |

## Outputs

| Output | Description |
|--------|-------------|
| `pr-url` | URL of the created pull request |
| `pr-number` | Number of the created pull request |
| `migrations-count` | Number of migrations performed |
| `files-changed` | Number of files changed |
| `risk-level` | Overall risk level of the migration |
| `test-passed` | Whether tests passed after migration |
| `json-report` | Path to the JSON report file |

## Example Workflows

### Weekly Scheduled Migration (Tier 1 Only)

Runs every Monday, applies only deterministic AST transforms, and opens a PR.

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

      - uses: Ragab-Technologies/codeshift@v1
        id: codeshift
        with:
          github-token: ${{ secrets.GITHUB_TOKEN }}
          tier1-only: 'true'
          run-tests: 'true'
          test-command: 'pytest'

      - name: Summary
        if: steps.codeshift.outputs.migrations-count != '0'
        run: |
          echo "Migrations: ${{ steps.codeshift.outputs.migrations-count }}"
          echo "Files changed: ${{ steps.codeshift.outputs.files-changed }}"
          echo "Risk level: ${{ steps.codeshift.outputs.risk-level }}"
          echo "PR: ${{ steps.codeshift.outputs.pr-url }}"
```

### Manual Dispatch with Configurable Options

Trigger manually from the Actions tab with selectable options.

```yaml
name: Manual Migration
on:
  workflow_dispatch:
    inputs:
      libraries:
        description: 'Libraries to migrate (comma-separated, empty for all)'
        required: false
        default: ''
      tier1-only:
        description: 'Tier 1 only (deterministic transforms)'
        type: boolean
        default: true
      max-risk-level:
        description: 'Maximum risk level'
        type: choice
        options:
          - low
          - medium
          - high
        default: medium

permissions:
  contents: write
  pull-requests: write

jobs:
  migrate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: Ragab-Technologies/codeshift@v1
        with:
          github-token: ${{ secrets.GITHUB_TOKEN }}
          libraries: ${{ github.event.inputs.libraries }}
          tier1-only: ${{ github.event.inputs.tier1-only }}
          max-risk-level: ${{ github.event.inputs.max-risk-level }}
```

### PR Dependency Scan

Triggered when dependency files change in a PR. Posts scan results as a comment.

```yaml
name: Dependency Scan
on:
  pull_request:
    paths:
      - 'requirements*.txt'
      - 'pyproject.toml'
      - 'setup.cfg'
      - 'Pipfile'

permissions:
  contents: read
  pull-requests: write

jobs:
  scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: Ragab-Technologies/codeshift@v1
        id: codeshift
        with:
          github-token: ${{ secrets.GITHUB_TOKEN }}
          create-pr: 'false'
          run-tests: 'false'
          tier1-only: 'true'

      - name: Comment on PR
        if: steps.codeshift.outputs.migrations-count != '0'
        uses: actions/github-script@v7
        with:
          script: |
            github.rest.issues.createComment({
              issue_number: context.issue.number,
              owner: context.repo.owner,
              repo: context.repo.repo,
              body: `## Codeshift Scan Results\n\n` +
                `Found **${{ steps.codeshift.outputs.migrations-count }}** available migration(s) ` +
                `affecting **${{ steps.codeshift.outputs.files-changed }}** file(s).\n\n` +
                `Risk level: **${{ steps.codeshift.outputs.risk-level }}**\n\n` +
                `Run \`codeshift upgrade-all --tier1-only\` locally or trigger the migration workflow to apply.`
            })
```

## Permissions

The action requires the following GitHub token permissions:

| Permission | Scope | Reason |
|------------|-------|--------|
| `contents` | `write` | Push migration branches |
| `pull-requests` | `write` | Create pull requests |

If using the default `GITHUB_TOKEN`, add a `permissions` block to your workflow:

```yaml
permissions:
  contents: write
  pull-requests: write
```

If using a Personal Access Token (PAT), ensure it has `repo` scope.

## Troubleshooting

### Action outputs are empty

Ensure you are **not** overriding the `GITHUB_OUTPUT` environment variable in your workflow. The runner provides this automatically.

### No migrations found

- Check that your project has a `requirements.txt`, `pyproject.toml`, or `setup.cfg` with dependency version pins.
- Run `codeshift scan` locally to verify outdated dependencies exist.
- If using `tier1-only: 'true'` (default), only the 15 supported libraries are eligible.

### PR creation fails

- Verify the `github-token` has `contents: write` and `pull-requests: write` permissions.
- Check that the `base-branch` input matches your repository's default branch.
- Ensure `gh` CLI is available (it's pre-installed on GitHub-hosted runners).

### Tests fail after migration

- The action uses `continue-on-error` for the test step, so test failures won't block PR creation.
- Review the test output in the Actions log and the PR description for details.
- Test results are included in the PR body and step summary.

### Tier 2/3 migrations

To use LLM-powered migrations, provide a Codeshift API key and disable `tier1-only`:

```yaml
- uses: Ragab-Technologies/codeshift@v1
  with:
    github-token: ${{ secrets.GITHUB_TOKEN }}
    codeshift-api-key: ${{ secrets.CODESHIFT_API_KEY }}
    tier1-only: 'false'
```
