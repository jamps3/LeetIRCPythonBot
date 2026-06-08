#!/usr/bin/env python3
"""
Setup script to install Git hooks for the LeetIRCPythonBot project.

This script generates and installs the pre-commit hook.
"""

import os
import stat


def get_hook_content():
    r"""Generate the pre-commit hook content."""
    return r"""#!/bin/bash
# LeetIRCPythonBot Pre-commit Hook
# Formats and lints code with Ruff via uv, then runs quick tests if PRECOMMIT_RUN_TESTS enabled.
# If any step fails, the commit is aborted.

set -euo pipefail

echo "Running pre-commit: Ruff format and lint..."

# Ensure we run in repo root
REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

if ! command -v uv >/dev/null 2>&1; then
  echo "uv not found. Install it from:"
  echo "https://docs.astral.sh/uv/getting-started/installation/"
  exit 1
fi

echo "Using uv: $(uv --version)"

# Run Ruff if available, fail if not found
if uv run ruff --version >/dev/null 2>&1; then
  # Get list of staged Python files to only format those
  STAGED_FILES=$(git diff --cached --name-only --diff-filter=ACM | { grep -E '\.py$' || true; } | tr '\n' ' ')
  if [ -n "$STAGED_FILES" ]; then
    echo "uv run ruff format $STAGED_FILES"
    uv run ruff format $STAGED_FILES

    echo "uv run ruff check --fix $STAGED_FILES"
    uv run ruff check --fix $STAGED_FILES

    # Re-stage only the originally staged files that were modified
    echo "Re-staging formatted files..."
    git add $STAGED_FILES
  else
    echo "No staged Python files to format"
  fi
else
  echo "ERROR: Ruff not found. Run: uv sync --dev"
  exit 1
fi

echo "uv run ruff check ."
uv run ruff check .

# Optionally run tests if PRECOMMIT_RUN_TESTS is enabled
if [ "${PRECOMMIT_RUN_TESTS:-0}" != "0" ]; then
  echo "Running tests (PRECOMMIT_RUN_TESTS enabled)..."
  uv run pytest -q
  TEST_STATUS=$?
  if [ $TEST_STATUS -ne 0 ]; then
    echo "Tests failed! Commit aborted."
    echo "Fix the failing tests or use 'git commit --no-verify' to bypass"
    exit 1
  fi
fi

# Increment version number as part of the commit
echo "Incrementing version number..."
uv run python -c "
import os
import re

version_file = 'VERSION'

# Only proceed if VERSION file exists
if os.path.exists(version_file):
    # Read current version
    try:
        with open(version_file, 'r', encoding='utf-8') as f:
            current_version = f.read().strip()
    except (IOError, OSError):
        print('Could not read VERSION file')
        exit(0)

    # Parse version components (major.minor.patch)
    version_match = re.match(r'([0-9]+)\.([0-9]+)\.([0-9]+)$', current_version)
    if version_match:
        major, minor, patch = version_match.groups()
        minor = int(minor)
        patch = int(patch)

        # Bump minor version after 2.3.99, otherwise bump patch
        if minor == 3 and patch >= 99:
            # Go from 2.3.99 to 2.4.0
            new_major = int(major)
            new_minor = minor + 1
            new_patch = 0
        elif patch >= 99:
            # For other versions, bump minor when patch reaches 99
            new_major = int(major)
            new_minor = minor + 1
            new_patch = 0
        else:
            # Normal patch increment
            new_major = int(major)
            new_minor = minor
            new_patch = patch + 1

        new_version = '{}.{}.{}'.format(new_major, new_minor, new_patch)

        # Write new version back to file
        try:
            with open(version_file, 'w', encoding='utf-8') as f:
                f.write(new_version + chr(10))
                print('Version incremented to {}'.format(new_version))
        except (IOError, OSError):
            print('Could not write to VERSION file')
    else:
        print('Invalid version format: {}'.format(current_version))
else:
    print('VERSION file not found, skipping version increment')
"

# Stage the VERSION file if it was modified
if git diff --quiet VERSION 2>/dev/null; then
    echo "VERSION file unchanged, skipping stage"
else
    echo "Staging VERSION file..."
    git add VERSION
fi

echo "All checks passed! Proceeding with commit."
exit 0
"""


def install_hook():
    """Install the pre-commit hook."""
    hook_content = get_hook_content()
    hook_path = os.path.join(".git", "hooks", "pre-commit")

    hooks_dir = os.path.dirname(hook_path)
    if not os.path.exists(hooks_dir):
        os.makedirs(hooks_dir)

    with open(hook_path, "w", encoding="utf-8") as f:
        f.write(hook_content)

    os.chmod(
        hook_path,
        stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH,  # noqa: S103 - Git hooks must be executable by the current user.
    )

    print(f"Pre-commit hook installed at: {hook_path}")
    print("The hook will run Ruff format and lint before each commit.")


if __name__ == "__main__":
    install_hook()
