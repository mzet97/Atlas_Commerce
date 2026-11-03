import { expect, test } from "@playwright/test";

/**
 * M7 recommendations E2E: only allowlisted + ACTIVE offers surface.
 * Precondition: offer-8c1634c75e12 ("Cafeteira M2") allowlisted via
 * Control (see EVD-007-001); M6/E2E offers stay out.
 */
test("recommendations show the allowlisted product only", async ({ page }) => {
  await page.goto("/recommendations");
  await expect(page.getByText("Cafeteira M2").first()).toBeVisible();
  await expect(page.getByText("Item M6")).toHaveCount(0);
  await expect(page.getByText("Item Ship")).toHaveCount(0);
});
