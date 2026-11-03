import type { MetadataRoute } from "next";
import { SEO_ORIGIN } from "@/lib/i18n";

export default function robots(): MetadataRoute.Robots {
  return {
    rules: { userAgent: "*", allow: "/", disallow: ["/callback", "/logout", "/locale"] },
    sitemap: `${SEO_ORIGIN}/sitemap.xml`,
  };
}
