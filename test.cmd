@echo off
setlocal

set "EXTRA_ARGS="

REM Ensure warnings module is available for xdist workers (Python 3.14 compatibility)
set PYTHONPATH=%PYTHONPATH%;%CD%
python -c "import warnings; print('warnings module loaded:', hasattr(warnings, '__name__'))"

REM Add -n 8 if pytest-xdist is available
python -c "import importlib.util, sys; sys.exit(0 if importlib.util.find_spec('xdist') else 1)"
if %ERRORLEVEL% EQU 0 set "EXTRA_ARGS=%EXTRA_ARGS% -q -n 12"

REM Add coverage flags if pytest-cov is available
python -c "import importlib.util, sys; sys.exit(0 if importlib.util.find_spec('pytest_cov') else 1)"
if %ERRORLEVEL% EQU 0 set "EXTRA_ARGS=%EXTRA_ARGS% --cov --cov-config=.coveragerc"

python -m pytest %EXTRA_ARGS% %*
set EXITCODE=%ERRORLEVEL%
endlocal & exit /b %EXITCODE%
