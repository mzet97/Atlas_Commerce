import { expect, test } from "@playwright/test";

/** M5 i18n E2E: locale switcher swaps catalog titles + UI chrome. */
test("locale switch renders localized titles and chrome", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("link", { name: "entrar" })).toBeVisible();
  await page.goto("/locale/es-ES");
  await page.waitForURL("http://localhost:3100/");
  await expect(page.getByRole("heading", { name: /catálogo/ })).toContainText("catálogo");
  await expect(page.getByText("Cafetera M2").first()).toBeVisible();
  await expect(page.getByText("para ti")).toBeVisible();
  await page.goto("/locale/en-US");
  await page.waitForURL("http://localhost:3100/");
  await expect(page.getByText("M2 Coffee Maker").first()).toBeVisible();
  await expect(page.getByText("for you")).toBeVisible();
  await page.goto("/locale/pt-BR");
  await page.waitForURL("http://localhost:3100/");
  await expect(page.getByText("Cafeteira M2").first()).toBeVisible();
});
