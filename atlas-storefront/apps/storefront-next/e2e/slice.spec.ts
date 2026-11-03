import { expect, test } from "@playwright/test";

/**
 * M2 slice E2E: the storefront lists what the command channel published.
 * Data precondition: the slice E2E script created "Cafeteira M2" with a
 * price and stock (see sdd/evidence/EVD-002-003).
 */
test("published product appears with price and availability", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText("Cafeteira M2").first()).toBeVisible();
  await expect(page.getByText("129.90 BRL").first()).toBeVisible();
  await expect(page.getByText("7 un.").first()).toBeVisible();
});

test("future version shows the syncing badge", async ({ page }) => {
  await page.goto("/?v=99");
  await expect(page.getByText("sincronizando…").first()).toBeVisible();
});
