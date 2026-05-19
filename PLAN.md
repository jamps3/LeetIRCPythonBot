# Ruff Cleanup Plan

## Goal

Make `ruff format --check --diff .` and `ruff check .` pass for the whole
repository after switching from Black, isort, and Flake8 to Ruff.

## Steps

1. Commit the Ruff migration separately.
2. Apply mechanical Ruff formatting across the repository.
3. Apply safe Ruff auto-fixes with `ruff check --fix .`.
4. Manually fix remaining lint issues:
   - Bare `except` handlers in debug scripts.
   - Undefined variable in `src/debug/scrape_nimipaivat.py`.
   - Ambiguous variable name in `src/tui.py`.
5. Run full Ruff format and lint checks.
6. Commit the cleanup separately.
