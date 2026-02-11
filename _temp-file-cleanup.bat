@echo off
echo =======================================================
echo          Cleaning up project temporary files
echo =======================================================

echo.
echo Cleaning Python cache directories (__pycache__)...
for /d /r . %%d in (__pycache__) do (
    if exist "%%d" (
        echo Deleting %%d
        rd /s /q "%%d"
    )
)

echo.
echo Cleaning .pyc files...
del /s /q *.pyc 2>nul

echo.
echo Cleaning build artifacts...
if exist "dist" (
    echo Deleting dist
    rd /s /q "dist"
)
if exist "build" (
    echo Deleting build
    rd /s /q "build"
)
if exist "*.spec" (
    echo Deleting *.spec
    del /q *.spec
)
if exist "*.egg-info" (
    echo Deleting *.egg-info
    rd /s /q "*.egg-info"
)

echo.
echo Cleaning test cache...
if exist ".pytest_cache" (
    echo Deleting .pytest_cache
    rd /s /q ".pytest_cache"
)
if exist ".mypy_cache" (
    echo Deleting .mypy_cache
    rd /s /q ".mypy_cache"
)
if exist ".coverage" (
    echo Deleting .coverage
    del /q .coverage
)
if exist "htmlcov" (
    echo Deleting htmlcov
    rd /s /q "htmlcov"
)

echo.
echo Cleaning logs and traceroutes...
if exist "*.log" (
    echo Deleting *.log
    del /q *.log
)
if exist "traceroutes\traceroute_*.txt" (
    echo Deleting traceroutes\traceroute_*.txt
    del /q "traceroutes\traceroute_*.txt"
)

echo.
echo =======================================================
echo                 Cleanup Complete!
echo =======================================================
pause
