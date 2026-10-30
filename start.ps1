# Windows PowerShell launcher: backend on :8000 (new window) and frontend on :5173.
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location "$Root\backend"
if (-not (Test-Path ".venv")) { python -m venv .venv }
& .\.venv\Scripts\python.exe -m pip install -q -r requirements.txt
Start-Process -FilePath ".\.venv\Scripts\python.exe" -ArgumentList "-m uvicorn app.main:app --host 127.0.0.1 --port 8000" -WorkingDirectory "$Root\backend"
Set-Location "$Root\frontend"
if (-not (Test-Path "node_modules")) { npm install --no-audit --no-fund }
Write-Host "API      -> http://127.0.0.1:8000/docs"
Write-Host "Frontend -> http://localhost:5173"
npm run dev
