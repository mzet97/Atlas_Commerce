# atlas-offers — Offer/Pricing owner (M2 slice)

Owns `Offer` aggregates: at most one ACTIVE offer per
(sku, seller, market, channel) with overlapping validity. Writes validate
here; the Control only forwards commands.

Endpoints: `POST /offers` (publish), `POST /offers/{id}/price`,
`POST /offers/{id}/deactivate`, `GET /offers/{id}` (owner read).
Events: `OfferPublished`, `PriceChanged`, `OfferDeactivated`.
