import { expect, test } from "@playwright/test";

/**
 * M5 search E2E: the storefront searches the PG projection (trigram).
 * Data precondition: "Cafeteira M2" is projected (see slice.spec.ts).
 */
test("search finds the projected product", async ({ page }) => {
  await page.goto("/search?q=Cafeteira");
  await expect(page.getByText("Cafeteira M2").first()).toBeVisible();
});

test("empty query shows the hint, not the catalog", async ({ page }) => {
  await page.goto("/search");
  await expect(page.getByText("Digite um termo").first()).toBeVisible();
});
