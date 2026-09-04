@echo off
title Push AI_Project to GitHub
echo =======================================================================
echo   Pushing AI_Project to https://github.com/selvaraj-95/AI_Project
echo =======================================================================
echo.

set "GIT_CMD=C:\Users\selvaraj\AppData\Local\github-copilot-git-2.53.0-4\cmd\git.exe"
cd /d "%~dp0"

echo 1. Staging all files...
"%GIT_CMD%" add .

echo 2. Committing changes...
"%GIT_CMD%" commit -m "AI_Project: Enterprise Risk Intelligence Assistant complete source code" >nul 2>&1

echo 3. Setting main branch and remote...
"%GIT_CMD%" branch -M main
"%GIT_CMD%" remote set-url origin https://github.com/selvaraj-95/AI_Project.git >nul 2>&1 || "%GIT_CMD%" remote add origin https://github.com/selvaraj-95/AI_Project.git >nul 2>&1

echo 4. Uploading to GitHub...
echo (If a GitHub sign-in window appears, please click Sign in / Authorize)
echo.

"%GIT_CMD%" push -u origin main

if %ERRORLEVEL% equ 0 (
    echo.
    echo =======================================================================
    echo   SUCCESS! All code is now published to your GitHub repository:
    echo   https://github.com/selvaraj-95/AI_Project
    echo =======================================================================
) else (
    echo.
    echo =======================================================================
    echo   If upload failed:
    echo   1. Please ensure you have created the repository "AI_Project" at:
    echo      https://github.com/new (Name: AI_Project)
    echo   2. Run this script again.
    echo =======================================================================
)

echo.
pause
