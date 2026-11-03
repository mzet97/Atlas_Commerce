import { listProductsWithOffers } from "@/lib/db";
import { formatMoney, getLocale, t } from "@/lib/i18n";

export const dynamic = "force-dynamic";

export default async function Home({
  searchParams,
}: {
  searchParams: Promise<{ v?: string }>;
}) {
  const locale = await getLocale();
  const expected = Number((await searchParams).v ?? NaN);
  const products = await listProductsWithOffers(locale);
  return (
    <main>
      <h1>{t(locale, "home.title")}</h1>
      <p className="note">{t(locale, "home.note")}</p>
      {products.length === 0 ? (
        <p>{t(locale, "home.empty")}</p>
      ) : (
        <ul>
          {products.map((p) => {
            const publishing =
              Number.isFinite(expected) && p.projection_version < expected;
            const available = p.status === "PUBLISHED" ? p.total_available : 0;
            return (
              <li key={p.product_id}>
                <div>
                  <strong>{p.title}</strong>
                  <span className="st">{p.status}</span>
                  {publishing && (
                    <span className="st">{t(locale, "home.syncing")}</span>
                  )}
                </div>
                <div>
                  {formatMoney(p.price_minor, p.currency, locale)}
                  {" · "}
                  {available > 0
                    ? t(locale, "unit.units", { n: available })
                    : t(locale, "unit.unavailable")}
                </div>
                <div className="pid">
                  {p.product_id} · v{p.projection_version}
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </main>
  );
}
