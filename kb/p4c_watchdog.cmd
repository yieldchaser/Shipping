@echo off
REM Relaunch the P4c bulk fleet if none is alive. No-op when the supervisor/daemon is running.
REM Used by the logon startup shortcut (and any scheduled task) so the launch path lives in one place.
"C:\Users\Dell\AppData\Local\Programs\Python\Python312\pythonw.exe" -X utf8 "C:\Users\Dell\Github\Shipping\kb\p4c_watchdog.py"
