import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  testDir: './tests',
  timeout: 30_000,
  retries: 0,
  use: {
    baseURL: 'http://localhost:5173',
  },
  webServer: [
    {
      command: 'pip install -r ../backend/requirements.txt && uvicorn backend.server:app --host 0.0.0.0 --port 8080',
      cwd: '..',
      port: 8080,
      timeout: 60_000,
      reuseExistingServer: true,
      env: {
        GOOGLE_API_KEY: 'dummy',
        FIREBASE_PROJECT_ID: 'dummy',
        GCS_BUCKET_NAME: 'dummy',
      },
    },
    {
      command: 'npm ci && npm run build && npm run preview -- --port 5173',
      cwd: '../frontend',
      port: 5173,
      timeout: 60_000,
      reuseExistingServer: true,
    },
  ],
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
  ],
})
