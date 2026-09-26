import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "./tests/e2e",
  workers: 1,
  retries: 0,
  timeout: 60000,
  use: {
    baseURL: "http://127.0.0.1:3001",
    browserName: "chromium",
    viewport: { width: 1440, height: 1000 },
    screenshot: "only-on-failure",
  },
});
