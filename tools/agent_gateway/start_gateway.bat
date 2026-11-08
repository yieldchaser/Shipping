@echo off
REM Starts the local agent gateway for DeepSeek Harness on http://127.0.0.1:4100/v1
start "agent-gateway" /min python "%~dp0agent_gateway.py"
