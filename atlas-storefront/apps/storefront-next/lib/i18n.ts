/**
 * i18n core (M5): mercado ≠ locale ≠ moeda (REQ-I18N-001). The locale
 * lives in a cookie set by /locale/<code>; catalog titles fall back to
 * pt-BR; prices render via Intl per locale+currency.
 */

import { cookies } from "next/headers";

export const LOCALES = ["pt-BR", "en-US", "es-ES"] as const;
export type Locale = (typeof LOCALES)[number];
export const DEFAULT_LOCALE: Locale = "pt-BR";
export const LOCALE_COOKIE = "atlas_locale";

/** Server-side locale resolution (cookie with pt-BR fallback). */
export async function getLocale(): Promise<Locale> {
  const value = (await cookies()).get(LOCALE_COOKIE)?.value;
  return isLocale(value) ? value : DEFAULT_LOCALE;
}

export function isLocale(value: string | undefined | null): value is Locale {
  return !!value && (LOCALES as readonly string[]).includes(value);
}

const STRINGS: Record<Locale, Record<string, string>> = {
  "pt-BR": {
    "nav.search": "buscar",
    "nav.recommendations": "para você",
    "auth.signin": "entrar",
    "auth.signout": "sair",
    "search.title": "Buscar no catálogo",
    "search.hint": "Digite um termo para buscar na projeção do catálogo.",
    "search.none": "Nenhum produto",
    "search.facets.price": "Preço",
    "search.facets.market": "Mercado",
    "search.pagination.prev": "anterior",
    "search.pagination.next": "próxima",
    "search.page": "Página {page}",
    "home.title": "Atlas Storefront — catálogo",
    "home.note":
      "Leitura das projeções PostgreSQL, derivadas de eventos de domínio. A disponibilidade aqui é indicativa: o checkout revalida no serviço Inventory autoritativo (INV-CQRS-001).",
    "home.empty": "Nenhum produto projetado ainda.",
    "home.syncing": "sincronizando…",
    "unit.units": "{n} un.",
    "unit.unavailable": "indisponível",
    "recs.title": "Para você",
  },
  "en-US": {
    "nav.search": "search",
    "nav.recommendations": "for you",
    "auth.signin": "sign in",
    "auth.signout": "sign out",
    "search.title": "Search the catalog",
    "search.hint": "Type a term to search the catalog projection.",
    "search.none": "No products",
    "search.facets.price": "Price",
    "search.facets.market": "Market",
    "search.pagination.prev": "previous",
    "search.pagination.next": "next",
    "search.page": "Page {page}",
    "home.title": "Atlas Storefront — catalog",
    "home.note":
      "Reads come from PostgreSQL projections derived from domain events. Availability here is indicative: checkout revalidates against the authoritative Inventory service (INV-CQRS-001).",
    "home.empty": "No projected products yet.",
    "home.syncing": "syncing…",
    "unit.units": "{n} units",
    "unit.unavailable": "unavailable",
    "recs.title": "For you",
  },
  "es-ES": {
    "nav.search": "buscar",
    "nav.recommendations": "para ti",
    "auth.signin": "entrar",
    "auth.signout": "salir",
    "search.title": "Buscar en el catálogo",
    "search.hint": "Escribe un término para buscar en la proyección del catálogo.",
    "search.none": "Sin productos",
    "search.facets.price": "Precio",
    "search.facets.market": "Mercado",
    "search.pagination.prev": "anterior",
    "search.pagination.next": "siguiente",
    "search.page": "Página {page}",
    "home.title": "Atlas Storefront — catálogo",
    "home.note":
      "Las lecturas vienen de proyecciones PostgreSQL derivadas de eventos de dominio. La disponibilidad aquí es indicativa: el checkout revalida en el servicio Inventory autoritativo (INV-CQRS-001).",
    "home.empty": "Aún no hay productos proyectados.",
    "home.syncing": "sincronizando…",
    "unit.units": "{n} uds.",
    "unit.unavailable": "no disponible",
    "recs.title": "Para ti",
  },
};

export function t(locale: Locale, key: string, vars?: Record<string, string | number>): string {
  const template = STRINGS[locale][key] ?? STRINGS[DEFAULT_LOCALE][key] ?? key;
  if (!vars) return template;
  return Object.entries(vars).reduce(
    (acc, [name, value]) => acc.replace(`{${name}}`, String(value)),
    template,
  );
}

export function pickTitle(
  titles: Record<string, string> | null,
  fallback: string,
  locale: Locale,
): string {
  return (titles && titles[locale]) || fallback || "(sem título)";
}

export function formatMoney(
  priceMinor: number | null,
  currency: string | null,
  locale: Locale,
): string {
  if (priceMinor === null || currency === null) return "—";
  return new Intl.NumberFormat(locale, { style: "currency", currency })
    .format(priceMinor / 100);
}

export const SEO_ORIGIN =
  process.env.SEO_ORIGIN ?? "http://localhost:3100";
