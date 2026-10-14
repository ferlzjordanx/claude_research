import { defineConfig, devices } from "@playwright/test";

// Starts BOTH tiers, then drives a real browser against them:
// browser -> Vite dev server (:5173) -> /api proxy -> FastAPI (:8000).
// PYTHON lets you point at your backend virtualenv's interpreter.
const python = process.env.PYTHON ?? "python";

export default defineConfig({
  testDir: "./e2e",
  testMatch: "*.e2e.ts",
  fullyParallel: false,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? "github" : "list",
  use: {
    baseURL: "http://127.0.0.1:5173",
    trace: "retain-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: {
        ...devices["Desktop Chrome"],
        launchOptions: {
          // Pre-installed browser (e.g. CI image); otherwise run
          // `npx playwright install chromium` once.
          executablePath: process.env.PW_CHROMIUM_PATH || undefined,
        },
      },
    },
  ],
  webServer: [
    {
      command: `${python} -m uvicorn app.main:create_app --factory`,
      cwd: "../backend",
      url: "http://127.0.0.1:8000/health",
      reuseExistingServer: !process.env.CI,
      env: {
        APP_ENV: "dev",
        APP_JWT_SECRET: "e2e-secret-e2e-secret-e2e-secret-e2e!",
        APP_LOG_JSON: "false",
        APP_DATABASE_URL: "sqlite://", // fresh DB every run
        APP_DEMO_USERS:
          "agent:agent-password:agent," +
          "alice:alice-password:requester," +
          "bob:bob-password:requester",
      },
    },
    {
      command: "npx vite --port 5173 --strictPort --host 127.0.0.1",
      url: "http://127.0.0.1:5173",
      reuseExistingServer: !process.env.CI,
      env: { VITE_USE_MOCK: "false", VITE_API_BASE_URL: "/api" },
    },
  ],
});
