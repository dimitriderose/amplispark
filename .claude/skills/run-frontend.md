Start the Amplispark React/Vite frontend dev server locally.

## Steps

1. Check whether port 5173 is already in use:
   ```powershell
   Get-NetTCPConnection -LocalPort 5173 -State Listen -ErrorAction SilentlyContinue
   ```
   If a result is returned, tell the user "Port 5173 is already in use — the frontend may already be running." and stop.

2. Open a new PowerShell terminal window for the frontend:
   ```powershell
   Start-Process powershell -ArgumentList '-NoExit', '-Command', 'cd "C:\Users\dimit\Documents\GitHub\amplispark\frontend"; npm run dev'
   ```

3. Tell the user:
   - Frontend is starting in a new terminal window
   - App: http://localhost:5173
   - All `/api/*` calls are proxied to http://localhost:8080 (Vite proxy config)
   - HMR is active — edits appear instantly in the browser
