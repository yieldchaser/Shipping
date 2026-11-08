# Stores the Ultrafast API key in ~/.dsh/.credentials.yaml (local only, never in the repo).
# Run:  powershell -ExecutionPolicy Bypass -File tools\agent_gateway\set_ultrafast_key.ps1
$sec = Read-Host "Paste your Ultrafast key (ufk_...) and press Enter" -AsSecureString
$key = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($sec)).Trim()
if (-not $key.StartsWith("ufk_")) { Write-Host "That does not look like an Ultrafast key (should start with ufk_). Nothing changed."; exit 1 }
$f = Join-Path $HOME ".dsh\.credentials.yaml"
$lines = Get-Content $f | Where-Object { $_ -notmatch '^\s+ULTRAFAST_API_KEY:' }
$out = @(); foreach ($l in $lines) { $out += $l; if ($l -match '^refs:\s*$') { $out += "  ULTRAFAST_API_KEY: $key" } }
Set-Content -Path $f -Value $out -Encoding UTF8
Write-Host "Saved. Restarting the agent gateway..."
Get-CimInstance Win32_Process -Filter "Name='python.exe' or Name='pythonw.exe'" | Where-Object { $_.CommandLine -like '*agent_gateway.py*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
Start-Process -WindowStyle Hidden -FilePath "pythonw" -ArgumentList "`"$PSScriptRoot\agent_gateway.py`""
Start-Sleep 3
try { (Invoke-RestMethod http://127.0.0.1:4100/stats) | Format-List } catch { Write-Host "Gateway did not answer; run start_gateway.bat" }
