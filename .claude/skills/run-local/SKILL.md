---
name: run-local
description: Start both the Amplispark backend and frontend servers for local development. Use when the user wants to run the app locally, start the servers, or develop locally.
---
Start both the Amplispark backend and frontend for full-stack local development.

## Steps

1. Check whether port 8080 is already in use:
   ```powershell
   Get-NetTCPConnection -LocalPort 8080 -State Listen -ErrorAction SilentlyContinue
   ```
   If a result is returned, tell the user the backend is already running and skip step 2. Otherwise:

2. Open a new PowerShell terminal for the backend:
   ```powershell
   Start-Process powershell -ArgumentList '-NoExit', '-Command', 'cd "C:\Users\dimit\Documents\GitHub\amplispark"; .\backend\.venv\Scripts\uvicorn backend.server:app --host 0.0.0.0 --port 8080 --reload'
   ```
   Wait approximately 3 seconds to let uvicorn bind before starting the frontend.

3. Check whether port 5173 is already in use:
   ```powershell
   Get-NetTCPConnection -LocalPort 5173 -State Listen -ErrorAction SilentlyContinue
   ```
   If a result is returned, tell the user the frontend is already running and skip step 4. Otherwise:

4. Open a new PowerShell terminal for the frontend:
   ```powershell
   Start-Process powershell -ArgumentList '-NoExit', '-Command', 'cd "C:\Users\dimit\Documents\GitHub\amplispark\frontend"; npm run dev'
   ```

5. Tell the user:
   - Two terminal windows are now open (one per server)
   - Backend API: http://localhost:8080 — docs: http://localhost:8080/docs
   - Frontend app: http://localhost:5173
   - Frontend proxies `/api/*` to the backend automatically
   - Both servers hot-reload on file changes
