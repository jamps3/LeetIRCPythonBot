#!/usr/bin/env python3
"""
Setup Git Pre-commit Hooks for LeetIRC Bot

This script sets up git pre-commit hooks to run tests automatically before commits.
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
# LeetIRC Bot Pre-commit Hook
# Runs tests before allowing commits

echo "Running pre-commit tests..."

# Run the test suite
python test_framework.py --quick

# Check the exit status
if [ $? -ne 0 ]; then
    echo "Tests failed! Commit aborted."
    echo "Fix the failing tests or use 'git commit --no-verify' to bypass"
    exit 1
fi

echo "All tests passed! Proceeding with commit."
exit 0
"""

    try:
        with open(pre_commit_hook, "w", newline="\n") as f:
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


def create_requirements_txt():
    """Create requirements.txt for the project."""

    requirements = [
        "requests>=2.25.0",
        "beautifulsoup4>=4.9.0",
        "# Development dependencies",
        "# black>=22.0.0",
        "# flake8>=4.0.0",
        "# isort>=5.10.0",
        "# bandit>=1.7.0",
        "# safety>=2.0.0",
    ]

    try:
        with open("requirements.txt", "w") as f:
            f.write("\n".join(requirements) + "\n")

        print("Created requirements.txt")
        return True

    except Exception as e:
        print(f"Error creating requirements.txt: {e}")
        return False


def update_test_framework_for_quick_mode():
    """Update test framework to support --quick flag."""

    test_framework_path = Path("test_framework.py")

    if not test_framework_path.exists():
        print("test_framework.py not found")
        return False

    try:
        with open(test_framework_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Check if quick mode support already exists
        if "--quick" in content:
            print("Quick mode already supported in test framework")
            return True

        # Add quick mode support to main function
        old_main = """if __name__ == "__main__":
    main()"""

        new_main = """if __name__ == "__main__":
    import sys
    quick_mode = "--quick" in sys.argv
    main(quick_mode=quick_mode)"""

        if old_main in content:
            content = content.replace(old_main, new_main)

            # Also update the main function signature
            old_def = "def main():"
            new_def = "def main(quick_mode: bool = False):"
            content = content.replace(old_def, new_def)

            # Update the registration call
            old_register = "register_all_test_suites(runner)"
            new_register = "register_all_test_suites(runner, quick_mode=quick_mode)"
            content = content.replace(old_register, new_register)

            with open(test_framework_path, "w", encoding="utf-8") as f:
                f.write(content)

            print("Updated test framework with quick mode support")
            return True
        else:
            print("Could not find main function to update")
            return False

    except Exception as e:
        print(f"Error updating test framework: {e}")
        return False


def setup_git_config():
    """Setup git configuration for better commit messages."""

    try:
        # Set up commit message template with helpful hints
        commit_template = """# LeetIRC Bot Commit Message
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
# Remember: Tests run automatically before commit!
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

    print("Setting up LeetIRC Bot development environment...")
    print()

    success_count = 0
    total_steps = 4

    # Step 1: Create pre-commit hook
    print("1. Setting up pre-commit hook...")
    if create_pre_commit_hook():
        success_count += 1
    print()

    # Step 2: Create requirements.txt
    print("2. Creating requirements.txt...")
    if create_requirements_txt():
        success_count += 1
    print()

    # Step 3: Update test framework for quick mode
    print("3. Adding quick mode to test framework...")
    if update_test_framework_for_quick_mode():
        success_count += 1
    print()

    # Step 4: Setup git configuration
    print("4. Configuring git settings...")
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
        print("   - Run 'python test_framework.py' to test everything")
        print("   - Run 'python test_framework.py --quick' for fast tests")
        print("   - Tests will run automatically before each commit")
        print("   - Use 'git commit --no-verify' to bypass pre-commit tests")
    else:
        print("Some setup steps failed. Check the messages above.")
        print("You can run this script again to retry failed steps.")

    return success_count == total_steps


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
