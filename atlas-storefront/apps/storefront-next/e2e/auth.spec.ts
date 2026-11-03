import { expect, test } from "@playwright/test";

/**
 * TASK-001-010 E2E: real browser login via Keycloak authorization-code
 * flow with PKCE (S256). alice.customer is seeded by setup-realm.sh.
 */
test("login via redirect lands home with the username", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("link", { name: "entrar" }).click();
  await page.waitForURL(/realms\/atlas\/protocol\/openid-connect\/auth/);
  await page.fill("#username", "alice.customer");
  await page.fill("#password", "alice-dev-only");
  await page.click("#kc-login");
  await page.waitForURL("http://localhost:3100/");
  await expect(page.locator(".site-header .user")).toHaveText("alice.customer");
  await expect(page.getByRole("link", { name: "sair" })).toBeVisible();
});

test("state mismatch is rejected (no session)", async ({ page }) => {
  await page.goto("/callback?code=x&state=tampered");
  await expect(page).toHaveURL(/auth_error=1/);
  await expect(page.getByRole("link", { name: "entrar" })).toBeVisible();
});

test("logout clears the session", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("link", { name: "entrar" }).click();
  await page.waitForURL(/realms\/atlas\/protocol\/openid-connect\/auth/);
  await page.fill("#username", "alice.customer");
  await page.fill("#password", "alice-dev-only");
  await page.click("#kc-login");
  await page.waitForURL("http://localhost:3100/");
  await page.getByRole("link", { name: "sair" }).click();
  await page.waitForURL("http://localhost:3100/");
  await expect(page.getByRole("link", { name: "entrar" })).toBeVisible();
});
