@echo off
title Shipping Terminal - Stealth Fleet Sync
cd /d "%~dp0"
echo =======================================================================
echo   SHIPPING TERMINAL: MANUAL STEALTH FLEET SYNC TRIGGER
echo =======================================================================
echo.
python scripts\acquire\run_scheduled_fleet_sync.py --force
echo.
echo =======================================================================
echo   Sync process finished.
echo =======================================================================
pause
