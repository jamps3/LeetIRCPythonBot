#!/usr/bin/env python3
"""
Comprehensive Testing Framework for LeetIRC Bot

This module provides a complete testing framework that can be run automatically
after every commit or on-demand. It includes unit tests, integration tests,
and functional tests for all components.
"""

import sys
import os
import time
import traceback
import subprocess
from typing import List, Dict, Any, Callable, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import importlib.util


class TestResult(Enum):
    """Test result status."""

    PASS = "PASS"
    FAIL = "FAIL"
    SKIP = "SKIP"
    ERROR = "ERROR"


@dataclass
class TestCase:
    """Individual test case."""

    name: str
    description: str
    test_func: Callable[[], bool]
    category: str = "general"
    dependencies: List[str] = None
    timeout: int = 30

    def __post_init__(self):
        if self.dependencies is None:
            self.dependencies = []


@dataclass
class TestSuite:
    """Collection of test cases."""

    name: str
    description: str
    tests: List[TestCase]
    setup_func: Optional[Callable[[], bool]] = None
    teardown_func: Optional[Callable[[], bool]] = None


@dataclass
class TestReport:
    """Test execution report."""

    suite_name: str
    test_name: str
    result: TestResult
    duration: float
    message: str = ""
    error_details: str = ""


class TestRunner:
    """Main test runner with comprehensive reporting."""

    def __init__(self, verbose: bool = True):
        self.verbose = verbose
        self.reports: List[TestReport] = []
        self.suites: List[TestSuite] = []

    def add_suite(self, suite: TestSuite):
        """Add a test suite to the runner."""
        self.suites.append(suite)

    def run_all(self) -> bool:
        """Run all test suites and return overall success."""
        print("LeetIRC Bot - Comprehensive Test Suite")
        print("=" * 60)

        total_tests = sum(len(suite.tests) for suite in self.suites)
        print(f"Running {total_tests} tests across {len(self.suites)} suites...")
        print()

        overall_success = True

        for suite in self.suites:
            success = self._run_suite(suite)
            overall_success = overall_success and success

        # Generate summary report
        self._print_summary()

        return overall_success

    def _run_suite(self, suite: TestSuite) -> bool:
        """Run a single test suite."""
        print(f"Suite: {suite.name}")
        print(f"   {suite.description}")
        print("-" * 50)

        # Setup
        if suite.setup_func:
            if not self._run_safe(suite.setup_func, f"{suite.name} setup"):
                print(f"[FAIL] Suite setup failed, skipping {suite.name}")
                return False

        suite_success = True
        passed = 0

        for test in suite.tests:
            success = self._run_test(suite.name, test)
            if success:
                passed += 1
            else:
                suite_success = False

        # Teardown
        if suite.teardown_func:
            self._run_safe(suite.teardown_func, f"{suite.name} teardown")

        print(f"Stats: Suite Result: {passed}/{len(suite.tests)} tests passed")
        print()

        return suite_success

    def _run_test(self, suite_name: str, test: TestCase) -> bool:
        """Run a single test case."""
        if self.verbose:
            print(f"  Test: {test.name}... ", end="", flush=True)

        start_time = time.time()

        try:
            # Check dependencies
            for dep in test.dependencies:
                if not self._check_dependency(dep):
                    result = TestReport(
                        suite_name=suite_name,
                        test_name=test.name,
                        result=TestResult.SKIP,
                        duration=0,
                        message=f"Missing dependency: {dep}",
                    )
                    self.reports.append(result)
                    if self.verbose:
                        print(f"[SKIP]  SKIP (missing {dep})")
                    return True  # Skip doesn't count as failure

            # Run the test
            success = test.test_func()
            duration = time.time() - start_time

            if success:
                result = TestReport(
                    suite_name=suite_name,
                    test_name=test.name,
                    result=TestResult.PASS,
                    duration=duration,
                )
                if self.verbose:
                    print(f"[PASS] PASS ({duration:.3f}s)")
            else:
                result = TestReport(
                    suite_name=suite_name,
                    test_name=test.name,
                    result=TestResult.FAIL,
                    duration=duration,
                    message="Test returned False",
                )
                if self.verbose:
                    print(f"[FAIL] FAIL ({duration:.3f}s)")

            self.reports.append(result)
            return success

        except Exception as e:
            duration = time.time() - start_time
            error_details = traceback.format_exc()

            result = TestReport(
                suite_name=suite_name,
                test_name=test.name,
                result=TestResult.ERROR,
                duration=duration,
                message=str(e),
                error_details=error_details,
            )
            self.reports.append(result)

            if self.verbose:
                print(f"[ERROR] ERROR ({duration:.3f}s): {e}")

            return False

    def _run_safe(self, func: Callable, name: str) -> bool:
        """Run a function safely with error handling."""
        try:
            return func()
        except Exception as e:
            print(f"[FAIL] {name} failed: {e}")
            return False

    def _check_dependency(self, dep: str) -> bool:
        """Check if a dependency is available."""
        try:
            if dep.startswith("module:"):
                module_name = dep[7:]
                spec = importlib.util.find_spec(module_name)
                return spec is not None
            elif dep.startswith("file:"):
                file_path = dep[5:]
                return os.path.exists(file_path)
            elif dep.startswith("env:"):
                env_var = dep[4:]
                return os.getenv(env_var) is not None
            else:
                # Custom dependency checks can be added here
                return True
        except Exception:
            return False

    def _print_summary(self):
        """Print comprehensive test summary."""
        print("=" * 60)
        print("Stats: TEST SUMMARY")
        print("=" * 60)

        # Count results by status
        counts = {result: 0 for result in TestResult}
        for report in self.reports:
            counts[report.result] += 1

        total = len(self.reports)
        passed = counts[TestResult.PASS]
        failed = counts[TestResult.FAIL]
        errors = counts[TestResult.ERROR]
        skipped = counts[TestResult.SKIP]

        print(f"Total Tests: {total}")
        print(f"[PASS] Passed:   {passed}")
        print(f"[FAIL] Failed:   {failed}")
        print(f"[ERROR] Errors:   {errors}")
        print(f"[SKIP] Skipped:  {skipped}")

        if total > 0:
            success_rate = (passed / total) * 100
            print(f"Success Rate: Success Rate: {success_rate:.1f}%")

        # Show failed tests
        if failed > 0 or errors > 0:
            print("\nTest: FAILED TESTS:")
            for report in self.reports:
                if report.result in [TestResult.FAIL, TestResult.ERROR]:
                    print(
                        f"  [FAIL] {report.suite_name}.{report.test_name}: {report.message}"
                    )
                    if report.error_details and self.verbose:
                        print(
                            f"     Details: {report.error_details.split(chr(10))[-2] if chr(10) in report.error_details else report.error_details}"
                        )

        # Performance summary
        total_time = sum(r.duration for r in self.reports)
        avg_time = total_time / total if total > 0 else 0
        print(f"\nTime: Total Time: {total_time:.3f}s (avg: {avg_time:.3f}s per test)")

        # Overall result
        overall_success = failed == 0 and errors == 0
        print("\n" + "=" * 60)
        if overall_success:
            print("[SUCCESS] ALL TESTS PASSED!")
        else:
            print("[WARNING] SOME TESTS FAILED!")
        print("=" * 60)


def create_git_hook():
    """Create a git pre-commit hook to run tests automatically."""
    hook_content = """#!/bin/sh
# Pre-commit hook to run tests
echo "Running tests before commit..."
python test_framework.py --quick
if [ $? -ne 0 ]; then
    echo "[FAIL] Tests failed! Commit aborted."
    echo "Fix the failing tests or use 'git commit --no-verify' to skip tests."
    exit 1
fi
echo "[PASS] All tests passed!"
"""

    hook_path = ".git/hooks/pre-commit"

    try:
        os.makedirs(".git/hooks", exist_ok=True)

        with open(hook_path, "w") as f:
            f.write(hook_content)

        # Make it executable (Unix-style, but Git for Windows handles this)
        if os.name != "nt":  # Not Windows
            os.chmod(hook_path, 0o755)

        print(f"[PASS] Created git pre-commit hook at {hook_path}")
        return True

    except Exception as e:
        print(f"[FAIL] Failed to create git hook: {e}")
        return False


def create_github_workflow():
    """Create GitHub Actions workflow for CI/CD."""
    workflow_content = """name: LeetIRC Bot Tests

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
  test:
    runs-on: ubuntu-latest
    
    strategy:
      matrix:
        python-version: [3.9, 3.10, 3.11, 3.12]
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python ${{ matrix.python-version }}
      uses: actions/setup-python@v3
      with:
        python-version: ${{ matrix.python-version }}
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt
        pip install pytest coverage
    
    - name: Run comprehensive tests
      run: |
        python test_framework.py --ci
    
    - name: Generate coverage report
      run: |
        coverage run --source=. test_framework.py
        coverage xml
    
    - name: Upload coverage to Codecov
      uses: codecov/codecov-action@v3
      with:
        file: ./coverage.xml
        fail_ci_if_error: true
"""

    os.makedirs(".github/workflows", exist_ok=True)

    try:
        with open(".github/workflows/tests.yml", "w") as f:
            f.write(workflow_content)

        print("[PASS] Created GitHub Actions workflow at .github/workflows/tests.yml")
        return True

    except Exception as e:
        print(f"[FAIL] Failed to create GitHub workflow: {e}")
        return False


def main():
    """Main entry point for test framework."""
    import argparse

    parser = argparse.ArgumentParser(description="LeetIRC Bot Test Framework")
    parser.add_argument("--quick", action="store_true", help="Run only quick tests")
    parser.add_argument("--ci", action="store_true", help="Run in CI mode")
    parser.add_argument(
        "--setup-hooks", action="store_true", help="Setup git hooks and CI"
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--suite", help="Run specific test suite only")

    args = parser.parse_args()

    if args.setup_hooks:
        print("Setup: Setting up automated testing...")
        create_git_hook()
        create_github_workflow()
        print("[PASS] Automated testing setup complete!")
        return 0

    # Import and register all test suites
    runner = TestRunner(verbose=args.verbose or not args.ci)

    # Register test suites (will be implemented in separate files)
    try:
        from tests import register_all_test_suites

        register_all_test_suites(runner, quick_mode=args.quick)
    except ImportError:
        print("[WARNING] No test suites found. Run with --setup-hooks first.")
        return 1

    # Run tests
    if args.suite:
        # Run specific suite
        suite = next((s for s in runner.suites if s.name == args.suite), None)
        if suite:
            success = runner._run_suite(suite)
        else:
            print(f"[FAIL] Test suite '{args.suite}' not found")
            return 1
    else:
        # Run all suites
        success = runner.run_all()

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
