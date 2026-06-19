Start the Amplispark FastAPI backend server locally.

## Steps

1. Check whether port 8080 is already in use:
   ```powershell
   Get-NetTCPConnection -LocalPort 8080 -State Listen -ErrorAction SilentlyContinue
   ```
   If a result is returned, tell the user "Port 8080 is already in use — the backend may already be running." and stop.

2. Open a new PowerShell terminal window for the backend:
   ```powershell
   Start-Process powershell -ArgumentList '-NoExit', '-Command', 'cd "C:\Users\dimit\Documents\GitHub\amplispark"; .\backend\.venv\Scripts\uvicorn backend.server:app --host 0.0.0.0 --port 8080 --reload'
   ```

3. Tell the user:
   - Backend is starting in a new terminal window
   - API: http://localhost:8080
   - Interactive docs: http://localhost:8080/docs
   - Auto-reloads on file changes

**Note:** Must run from project root (not `backend/`) — module path is `backend.server:app` and the server uses `from backend.config import ...`.
