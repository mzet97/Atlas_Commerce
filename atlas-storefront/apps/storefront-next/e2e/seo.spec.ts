import { expect, test } from "@playwright/test";

/** M5 SEO E2E: sitemap, robots and hreflang/canonical alternates. */
test("sitemap and robots are served", async ({ request }) => {
  const sitemap = await request.get("/sitemap.xml");
  expect(sitemap.status()).toBe(200);
  expect(await sitemap.text()).toContain("loc>");
  const robots = await request.get("/robots.txt");
  expect(robots.status()).toBe(200);
  expect(await robots.text()).toContain("Sitemap:");
});

test("home exposes canonical + hreflang alternates", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator('link[rel="canonical"]')).toHaveCount(1);
  for (const lang of ["pt-BR", "en-US", "es-ES"]) {
    await expect(
      page.locator(`link[rel="alternate"][hreflang="${lang}"]`),
    ).toHaveCount(1);
  }
});
