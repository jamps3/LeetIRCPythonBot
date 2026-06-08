@echo off
REM Windows batch script that calls the Python test runner through uv
uv run python test %*
