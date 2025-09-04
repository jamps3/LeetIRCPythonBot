@echo off
setlocal
python -m pytest --cov --cov-config=.coveragerc %*
set EXITCODE=%ERRORLEVEL%
endlocal & exit /b %EXITCODE%

