@echo off
setlocal

set "EXTRA_ARGS="

REM Add -n auto if pytest-xdist is available
python -c "import importlib.util, sys; sys.exit(0 if importlib.util.find_spec('xdist') else 1)"
if %ERRORLEVEL% EQU 0 set "EXTRA_ARGS=%EXTRA_ARGS% -n auto"

REM Add coverage flags if pytest-cov is available
python -c "import importlib.util, sys; sys.exit(0 if importlib.util.find_spec('pytest_cov') else 1)"
if %ERRORLEVEL% EQU 0 set "EXTRA_ARGS=%EXTRA_ARGS% --cov --cov-config=.coveragerc"

python -m pytest %EXTRA_ARGS% %*
set EXITCODE=%ERRORLEVEL%
endlocal & exit /b %EXITCODE%
