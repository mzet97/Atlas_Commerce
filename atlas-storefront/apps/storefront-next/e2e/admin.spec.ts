import { expect, test } from "@playwright/test";

/**
 * M5 Admin E2E (Control Angular, port 4200): real OIDC login via redirect
 * (client atlas-control, public PKCE), then the finance module renders
 * with the operator identity. erin.finance = finance_analyst.
 */
test("admin signs in and reads the finance queue", async ({ page }) => {
  await page.goto("http://localhost:4200/");
  await page.getByTestId("signin").click();
  await page.waitForURL(/realms\/atlas\/protocol\/openid-connect\/auth/);
  await page.fill("#username", "erin.finance");
  await page.fill("#password", "erin-dev-only");
  await page.click("#kc-login");
  await page.waitForURL("http://localhost:4200/");
  await expect(page.getByTestId("user")).toContainText("erin.finance");
  await page.getByRole("link", { name: "finance" }).click();
  await expect(page.getByTestId("approvals")).toBeVisible();
});

test("admin shell exposes all ops modules", async ({ page }) => {
  await page.goto("http://localhost:4200/");
  for (const module of ["orders", "finance", "coupons", "returns"]) {
    await expect(
      page.getByRole("link", { name: module }),
    ).toBeVisible();
  }
});
