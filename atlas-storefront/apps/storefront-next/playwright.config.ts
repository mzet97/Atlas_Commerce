import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  timeout: 30000,
  use: { baseURL: process.env.STORE_URL ?? "http://localhost:3100" },
});
