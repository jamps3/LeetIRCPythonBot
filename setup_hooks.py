#!/usr/bin/env python3
"""
Setup script to install Git hooks for the LeetIRCPythonBot project.

This script generates and installs the pre-commit hook.
"""

import os
import stat


def get_hook_content():
    """Generate the pre-commit hook content."""
    return '''#!/bin/bash
# LeetIRCPythonBot Pre-commit Hook
# Formats code with isort and black, lints with flake8, then runs quick tests if PRECOMMIT_RUN_TESTS enabled.
# If any step fails, the commit is aborted.

set -euo pipefail

echo "Running pre-commit: isort, black and flake8..."

# Ensure we run in repo root
REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

# Function to find Python executable
find_python() {
  # Try different Python executables in order of preference
  for python_cmd in "python" "python3" "./venv/Scripts/python.exe" "./venv/bin/python"; do
    if command -v "$python_cmd" >/dev/null 2>&1; then
      # Test that Python actually works by running a simple command
      if "$python_cmd" -c "print('test')" >/dev/null 2>&1; then
        echo "$python_cmd"
        return 0
      fi
    fi
  done
  return 1
}

# Find Python executable
PYTHON_CMD=$(find_python)
if [ $? -ne 0 ]; then
  echo "❌ Python not found! Please ensure Python is installed and available in PATH."
  echo "   On Windows, you can install from the Microsoft Store or use a virtual environment."
  exit 1
fi

echo "Using Python: $PYTHON_CMD"

# Run isort if available
if $PYTHON_CMD -m isort --version >/dev/null 2>&1; then
  echo "$PYTHON_CMD -m isort ."
  $PYTHON_CMD -m isort .
else
  echo "isort not found, skipping (pip install isort)"
fi

# Run black if available
if $PYTHON_CMD -m black --version >/dev/null 2>&1; then
  echo "$PYTHON_CMD -m black ."
  $PYTHON_CMD -m black .
else
  echo "black not found, skipping (pip install black)"
fi

# Note: We don't auto-stage files here to avoid accidentally committing
# unintended changes. Run 'git add <files>' manually before commit.

# Run flake8 if available (lint errors should fail the commit)
if $PYTHON_CMD -m flake8 --version >/dev/null 2>&1; then
  echo "$PYTHON_CMD -m flake8 ."
  $PYTHON_CMD -m flake8 .
else
  echo "flake8 not found, skipping (pip install flake8)"
fi

# Optionally run tests if PRECOMMIT_RUN_TESTS is enabled
if [ "${PRECOMMIT_RUN_TESTS:-0}" != "0" ]; then
  echo "Running tests (PRECOMMIT_RUN_TESTS enabled)..."
  $PYTHON_CMD -m pytest -q
  TEST_STATUS=$?
  if [ $TEST_STATUS -ne 0 ]; then
    echo "Tests failed! Commit aborted."
    echo "Fix the failing tests or use 'git commit --no-verify' to bypass"
    exit 1
  fi
fi

# Increment version number as part of the commit
echo "Incrementing version number..."
$PYTHON_CMD -c "
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
    version_match = re.match(r'([0-9]+)\\\\.([0-9]+)\\\\.([0-9]+)$', current_version)
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

# Stage the version change
git add VERSION

echo "All checks passed! Proceeding with commit."
exit 0
'''


def setup_hooks():
    """Install the pre-commit hook."""
    # Get the directory where this script is located
    script_dir = os.path.dirname(os.path.abspath(__file__))

    # Ensure .git/hooks directory exists
    hooks_dir = os.path.join(script_dir, ".git", "hooks")
    os.makedirs(hooks_dir, exist_ok=True)

    hook_path = os.path.join(hooks_dir, "pre-commit")

    # Generate and write the hook content
    hook_content = get_hook_content()
    with open(hook_path, "w", encoding="utf-8") as f:
        f.write(hook_content)

    # Make it executable
    os.chmod(
        hook_path,
        os.stat(hook_path).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH,
    )

    print(f"Hook installed to: {hook_path}")


if __name__ == "__main__":
    setup_hooks()
