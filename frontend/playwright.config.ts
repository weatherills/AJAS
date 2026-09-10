import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  testDir: './e2e',
  testMatch: /.*\.playwright\.ts/,
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  use: {
    baseURL: 'http://127.0.0.1:3000',
    ...devices['Desktop Chrome'],
  },
  webServer: {
    command: 'npx vite --host 127.0.0.1 --port 3000 --strictPort',
    url: 'http://127.0.0.1:3000',
    reuseExistingServer: !process.env.CI,
    env: { VITE_USE_MOCK: 'true' },
  },
})
