import { listRecommendations } from "@/lib/db";
import { formatMoney, getLocale, t } from "@/lib/i18n";

export const dynamic = "force-dynamic";

export default async function Recommendations({
  searchParams,
}: {
  searchParams: Promise<{ customer_id?: string }>;
}) {
  const locale = await getLocale();
  const customerId = (await searchParams).customer_id;
  const items = await listRecommendations(locale, customerId);
  return (
    <main>
      <h1>{t(locale, "recs.title")}</h1>
      <p className="note">
        Somente ofertas ativas e curadas aparecem aqui. A disponibilidade é
        indicativa: o checkout revalida no Inventory autoritativo (INV-CQRS-001).
      </p>
      {items.length === 0 ? (
        <p>Nenhuma recomendação curada no momento.</p>
      ) : (
        <ul>
          {items.map((p) => (
            <li key={p.offer_id ?? p.product_id}>
              <div>
                <strong>{p.title}</strong>
                <span className="st">{p.status}</span>
              </div>
              <div>
                {formatMoney(p.price_minor, p.currency, locale)}
                {" · "}
                {p.total_available > 0
                  ? t(locale, "unit.units", { n: p.total_available })
                  : t(locale, "unit.unavailable")}
              </div>
              <div className="pid" data-testid="explanation">
                {p.explanation}
              </div>
            </li>
          ))}
        </ul>
      )}
      <p>
        <a href="/">← catálogo</a>
      </p>
    </main>
  );
}
