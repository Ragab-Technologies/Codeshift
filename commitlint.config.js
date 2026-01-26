module.exports = {
  extends: ['@commitlint/config-conventional'],
  rules: {
    'type-enum': [
      2,
      'always',
      [
        'feat',     // New feature
        'fix',      // Bug fix
        'docs',     // Documentation only
        'style',    // Code style (formatting, semicolons, etc)
        'refactor', // Code refactoring
        'perf',     // Performance improvement
        'test',     // Adding/updating tests
        'build',    // Build system or dependencies
        'ci',       // CI/CD changes
        'chore',    // Maintenance tasks
        'revert',   // Revert a commit
      ],
    ],
    'subject-case': [0],  // Disable - allows proper nouns like "Replit", "PyPI"
    'subject-empty': [2, 'never'],
    'type-empty': [2, 'never'],
  },
};
