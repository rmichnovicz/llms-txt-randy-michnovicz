import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "./e2e",
  workers: 1,
  use: {
    baseURL: "http://127.0.0.1:5175",
    channel: "chrome",
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
  },
  timeout: 45000,
  webServer: [
    {
      command: "../.venv/bin/python ../tests/browser_server.py",
      url: "http://127.0.0.1:8001/health",
      reuseExistingServer: false,
    },
    {
      command: "npm run dev -- --port 5175",
      url: "http://127.0.0.1:5175",
      env: { BRIEF_DEV_API: "http://127.0.0.1:8001" },
      reuseExistingServer: false,
    },
  ],
});
