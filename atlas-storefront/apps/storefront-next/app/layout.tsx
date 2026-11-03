import type { Metadata } from "next";
import { cookies } from "next/headers";
import { currentUser, SESSION_COOKIE } from "@/lib/auth";
import {
  getLocale,
  LOCALES,
  SEO_ORIGIN,
  t,
} from "@/lib/i18n";
import "./globals.css";

export async function generateMetadata(): Promise<Metadata> {
  const locale = await getLocale();
  const languages = Object.fromEntries(
    LOCALES.map((l) => [l, `${SEO_ORIGIN}/locale/${l}`]),
  );
  return {
    title: t(locale, "home.title"),
    description: t(locale, "home.note"),
    alternates: { canonical: SEO_ORIGIN, languages },
  };
}

export default async function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const locale = await getLocale();
  const user = await currentUser((await cookies()).get(SESSION_COOKIE)?.value);
  return (
    <html lang={locale}>
      <body>
        <header className="site-header">
          <a href="/" className="brand">Atlas</a>
          <nav>
            <a href="/search">{t(locale, "nav.search")}</a>
            <a href="/recommendations">{t(locale, "nav.recommendations")}</a>
            {user ? (
              <>
                <span className="user">{user}</span>
                <a href="/logout">{t(locale, "auth.signout")}</a>
              </>
            ) : (
              <a href="/login">{t(locale, "auth.signin")}</a>
            )}
            {LOCALES.map((code) => (
              <a key={code} href={`/locale/${code}`} className="locale-link">
                {code.slice(0, 2)}
              </a>
            ))}
          </nav>
        </header>
        {children}
      </body>
    </html>
  );
}
