import { defineConfig, devices } from "@playwright/test";

const webServer = process.env.PLAYWRIGHT_EXTERNAL_SERVERS ? undefined : [
  {
    command: "node e2e/api-server.cjs",
    url: "http://localhost:8106/health",
    reuseExistingServer: false,
    timeout: 120_000,
  },
  {
    command: "node node_modules/next/dist/bin/next dev -p 3106",
    url: "http://localhost:3106",
    reuseExistingServer: false,
    timeout: 120_000,
  },
];

export default defineConfig({
  testDir: "./e2e",
  outputDir: "../../var/web-test-results",
  fullyParallel: false,
  workers: 1,
  use: {
    baseURL: "http://localhost:3106",
    trace: "on-first-retry",
  },
  webServer,
  projects: [{name: "chromium", use: {...devices["Desktop Chrome"]}}],
});
