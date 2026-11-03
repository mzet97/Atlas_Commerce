import type { MetadataRoute } from "next";
import { LOCALES, SEO_ORIGIN } from "@/lib/i18n";

/** Static sitemap: shell + sections per locale (products render dynamic). */
export default function sitemap(): MetadataRoute.Sitemap {
  const paths = ["", "/search", "/recommendations"];
  return LOCALES.flatMap((locale) =>
    paths.map((path) => ({
      url: `${SEO_ORIGIN}${path}${path ? "" : `?locale=${locale}`}`,
      lastModified: new Date(),
    })),
  );
}
