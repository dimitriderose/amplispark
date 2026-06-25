import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  testDir: './tests',
  testMatch: '**/*.spec.ts',
  timeout: 30_000,
  retries: 0,
  expect: { timeout: 15_000 },
  use: {
    baseURL: 'http://localhost:5173',
  },
  webServer: {
    command: 'npm run build && npm run preview -- --port 5173',
    cwd: '../frontend',
    port: 5173,
    timeout: 120_000,
    reuseExistingServer: true,
  },
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
  ],
})
