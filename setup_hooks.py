#!/usr/bin/env python
"""
Setup Git Hooks for LeetIRCPythonBot

This script sets up comprehensive git hooks for the LeetIRCPythonBot project:
- Pre-commit hook: runs code formatting (isort, black), linting (flake8), and optional tests
- Pre-push hook: runs tests before allowing pushes to prevent broken code from being pushed
- Post-commit hook: automatically increments version numbers after each commit
- Git configuration: sets up commit message templates and helpful reminders

Run this script to initialize a complete development environment with automated quality checks.
"""

import os
import stat
import subprocess
import sys
from pathlib import Path


def create_pre_commit_hook():
    """Create a pre-commit hook that runs tests."""

    git_dir = Path(".git")
    if not git_dir.exists():
        print("Error: Not in a git repository")
        return False

    hooks_dir = git_dir / "hooks"
    hooks_dir.mkdir(exist_ok=True)

    pre_commit_hook = hooks_dir / "pre-commit"

    hook_content = """#!/bin/bash
# LeetIRCPythonBot Pre-commit Hook
# Formats code with isort and black, lints with flake8, then runs quick tests.
# If any step fails, the commit is aborted.

set -euo pipefail

echo "Running pre-commit: isort, black, flake8, and quick tests..."

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

# Re-stage any formatting changes
git add -A

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

echo "All checks passed! Proceeding with commit."
exit 0
"""

    try:
        with open(pre_commit_hook, "w", newline="\n", encoding="utf-8") as f:
            f.write(hook_content)

        # Make the hook executable
        if os.name != "nt":  # Unix-like systems
            st = os.stat(pre_commit_hook)
            os.chmod(pre_commit_hook, st.st_mode | stat.S_IEXEC)

        print(f"Pre-commit hook created: {pre_commit_hook}")
        return True

    except Exception as e:
        print(f"Error creating pre-commit hook: {e}")
        return False


def create_pre_push_hook():
    """Create a pre-push hook that runs tests before allowing push."""

    hooks_dir = Path(".git/hooks")
    if not hooks_dir.exists():
        print("Git hooks directory not found. Is this a git repository?")
        return False

    pre_push_hook = hooks_dir / "pre-push"

    hook_content = """#!/bin/bash
#
# Pre-push hook that runs all tests before allowing push
# If tests fail, the push is canceled
#
# This hook is called with the following parameters:
# $1 -- Name of the remote to which the push is being done
# $2 -- URL to which the push is being done
#
# If this script exits with a non-zero status, the push is aborted.

echo "🧪 Running tests before push..."
echo "⏳ This may take a moment..."

# Change to the repository root directory
REPO_ROOT=$(git rev-parse --show-toplevel)
cd "$REPO_ROOT" || exit 1

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

# Run tests using the test script
# Try different approaches for Windows compatibility
if [ -f "test" ]; then
    # Try running the test script directly
    if command -v pwsh >/dev/null 2>&1; then
        pwsh -ExecutionPolicy Bypass -Command "./test -q"
        test_exit_code=$?
    elif command -v powershell >/dev/null 2>&1; then
        powershell -ExecutionPolicy Bypass -Command "./test -q"
        test_exit_code=$?
    else
        # Fallback: run pytest directly
        $PYTHON_CMD -m pytest -q --disable-warnings
        test_exit_code=$?
    fi
else
    # Fallback: run pytest directly if test script doesn't exist
    $PYTHON_CMD -m pytest -q --disable-warnings
    test_exit_code=$?
fi

# Check if tests passed
if [ $test_exit_code -eq 0 ]; then
    echo "✅ All tests passed! Push allowed."
    exit 0
else
    echo "❌ Tests failed! Push canceled."
    echo "💡 Fix failing tests before pushing:"
    echo "   Run: .\\test (or $PYTHON_CMD -m pytest)"
    echo "   Then: git push"
    exit 1
fi
"""

    try:
        with open(pre_push_hook, "w", newline="\n", encoding="utf-8") as f:
            f.write(hook_content)

        # Make the hook executable
        if os.name != "nt":  # Unix-like systems
            st = os.stat(pre_push_hook)
            os.chmod(pre_push_hook, st.st_mode | stat.S_IEXEC)

        print(f"Pre-push hook created: {pre_push_hook}")
        return True

    except Exception as e:
        print(f"Error creating pre-push hook: {e}")
        return False


def create_post_commit_hook():
    """Create a post-commit hook that increments the version number."""

    hooks_dir = Path(".git/hooks")
    if not hooks_dir.exists():
        print("Git hooks directory not found. Is this a git repository?")
        return False

    post_commit_hook = hooks_dir / "post-commit"

    hook_content = """#!/usr/bin/env python
#
# Git post-commit hook to automatically increment version number
# Works on both Unix-like systems and Windows
#

import os
import re
import subprocess


def increment_version():
    '''Increment the patch version in VERSION file.'''

    version_file = "VERSION"

    # Only proceed if VERSION file exists
    if not os.path.exists(version_file):
        return

    # Read current version
    try:
        with open(version_file, "r", encoding="utf-8") as f:
            current_version = f.read().strip()
    except (IOError, OSError):
        print("Could not read VERSION file")
        return

    # Parse version components (major.minor.patch)
    version_match = re.match(r'^(\\d+)\\.(\\d+)\\.(\\d+)$', current_version)
    if not version_match:
        print(f"Invalid version format: {current_version}")
        return

    major, minor, patch = version_match.groups()

    # Increment patch version
    new_patch = int(patch) + 1
    new_version = f"{major}.{minor}.{new_patch}"

    # Write new version back to file
    try:
        with open(version_file, "w", encoding="utf-8") as f:
            f.write(new_version + "\\n")
    except (IOError, OSError):
        print("Could not write to VERSION file")
        return

    # Add the VERSION file to git for the next commit
    try:
        subprocess.run(["git", "add", "VERSION"], check=True, capture_output=True)
    except subprocess.CalledProcessError:
        print("Could not add VERSION file to git")
        return

    print(f"Version incremented to {new_version} (staged for next commit)")


if __name__ == "__main__":
    increment_version()
"""

    try:
        with open(post_commit_hook, "w", newline="\n", encoding="utf-8") as f:
            f.write(hook_content)

        # Make the hook executable
        if os.name != "nt":  # Unix-like systems
            st = os.stat(post_commit_hook)
            os.chmod(post_commit_hook, st.st_mode | stat.S_IEXEC)

        print(f"Post-commit hook created: {post_commit_hook}")
        return True

    except Exception as e:
        print(f"Error creating post-commit hook: {e}")
        return False


def setup_git_config():
    """Setup git configuration for better commit messages."""

    try:
        # Set up commit message template with helpful hints
        commit_template = """# LeetIRCPythonBot Commit Message
#
# Format: <type>(<scope>): <description>
#
# Types:
#   feat:     New feature
#   fix:      Bug fix
#   docs:     Documentation changes
#   style:    Code style changes (formatting, etc)
#   refactor: Code refactoring
#   test:     Adding or updating tests
#   chore:    Maintenance tasks
#
# Examples:
#   feat(weather): add UV index to weather service
#   fix(irc): resolve connection timeout issue
#   test(crypto): add comprehensive price formatting tests
#
# Remember: isort, black and flake8 are run automatically before commit and tests run automatically on push!
"""

        template_path = Path(".gitmessage")
        with open(template_path, "w") as f:
            f.write(commit_template)

        # Set git to use the template
        subprocess.run(
            ["git", "config", "commit.template", ".gitmessage"],
            check=True,
            capture_output=True,
        )

        print("Git commit message template configured")
        return True

    except subprocess.CalledProcessError:
        print("Could not configure git commit template")
        return False
    except Exception as e:
        print(f"Error setting up git config: {e}")
        return False


def main():
    """Main setup function."""

    print("Setting up LeetIRCPythonBot development environment...")
    print()

    success_count = 0
    total_steps = 4

    # Step 1: Create pre-commit hook
    print("1️⃣  Setting up pre-commit hook...")
    if create_pre_commit_hook():
        success_count += 1
    print()

    # Step 2: Create pre-push hook
    print("2️⃣  Setting up pre-push hook (runs tests before push)...")
    if create_pre_push_hook():
        success_count += 1
    print()

    # Step 3: Create post-commit hook
    print("3️⃣  Setting up post-commit hook (version incrementing)...")
    if create_post_commit_hook():
        success_count += 1
    print()

    # Step 4: Setup git configuration
    print("4️⃣  Configuring git settings...")
    if setup_git_config():
        success_count += 1
    print()

    # Summary
    print("=" * 60)
    print(f"Setup complete: {success_count}/{total_steps} steps successful")

    if success_count == total_steps:
        print("All development tools are ready!")
        print()
        print("Next steps:")
        print("   - Run '.\\test or python -m pytest' to test everything")
        print("   - Run 'python -m pytest -q' for fast tests")
        print(
            "   - To run tests on commit, set PRECOMMIT_RUN_TESTS=1 in your environment"
        )
        print("   - Tests run automatically before every push (cancels if they fail)")
        print("   - Version is automatically incremented after each commit")
        print("   - Use 'git commit --no-verify' to bypass pre-commit hooks")
        print(
            "   - Use 'git push --no-verify' to bypass pre-push hooks (not recommended)"
        )
    else:
        print("Some setup steps failed. Check the messages above.")
        print("You can run this script again to retry failed steps.")

    return success_count == total_steps


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
