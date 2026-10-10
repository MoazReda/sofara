@echo off
REM ---------------------------------------------------------------------------
REM  pull_bundle.bat - apply a commit bundle from Claude, safely.
REM
REM  Double-click it, or run from anywhere:   tools\pull_bundle.bat
REM  1. finds the newest .bundle (project folder first, then Downloads)
REM  2. refuses to run if you have uncommitted changes
REM  3. pulls, runs the tests, rebuilds the database
REM  4. shows the new commits and ASKS before pushing to GitHub
REM  5. deletes the bundle only after a successful push
REM  Close Excel first: an open CSV is locked and breaks the pull.
REM ---------------------------------------------------------------------------
setlocal
chcp 65001 >nul
cd /d "%~dp0.."

set "B="
for /f "delims=" %%F in ('dir /b /o-d "*.bundle" 2^>nul') do if not defined B set "B=%CD%\%%F"
if not defined B for /f "delims=" %%F in ('dir /b /o-d "%USERPROFILE%\Downloads\*.bundle" 2^>nul') do if not defined B set "B=%USERPROFILE%\Downloads\%%F"
if not defined B (
    echo [X] No .bundle file in the project folder or in Downloads.
    goto :end
)
echo [1/5] Bundle: "%B%"

git diff --quiet && git diff --cached --quiet
if errorlevel 1 (
    echo [X] You have uncommitted changes. Commit or discard them first:
    git status --short
    goto :end
)

echo [2/5] Pulling...
git pull "%B%" main
if errorlevel 1 ( echo [X] Pull failed. Is Excel open? Nothing was pushed. & goto :end )

echo [3/5] Running tests...
pytest
if errorlevel 1 ( echo [X] Tests failed. Nothing was pushed - send the output to Claude. & goto :end )

echo [4/5] Rebuilding the database...
sofara-build
if errorlevel 1 ( echo [X] Build failed. Nothing was pushed - send the output to Claude. & goto :end )

echo.
echo New commits not yet on GitHub:
git log --oneline origin/main..HEAD
echo.
set /p OK=[5/5] Push to GitHub? (y/n) 
if /i not "%OK%"=="y" ( echo Not pushed. The bundle is kept. & goto :end )
git push
if errorlevel 1 ( echo [X] Push failed. The bundle is kept. & goto :end )
del "%B%"
echo [OK] Done. Bundle deleted. Check CI: https://github.com/MoazReda/sofara/actions

:end
echo.
pause
