"use client";
import { FormEvent, useEffect, useState } from "react";
import { api, Detail, money } from "../lib/api";
import { Financing, Offer } from "../lib/financing";
import { ErrorNotice, Status, useApiError, useUser } from "./workspace";

const offerMoney = (offer: Offer) =>
  money({ face_value: offer.advance_amount, currency: offer.currency });
function expiryDefault() {
  const value = new Date(Date.now() + 2 * 86400000);
  return new Date(value.getTime() - value.getTimezoneOffset() * 60000)
    .toISOString()
    .slice(0, 16);
}
export function FinancingPanel({
  row,
  onChanged,
}: {
  row: Detail;
  onChanged: () => void;
}) {
  const user = useUser();
  const [data, setData] = useState<Financing | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [review, setReview] = useState<Offer | null>(null);
  const [refresh, setRefresh] = useState(0);
  const { error, setError, handle } = useApiError();
  useEffect(() => {
    let active = true;
    api<Financing>(`receivables/${row.id}/offers`)
      .then((result) => {
        if (active) setData(result);
      })
      .catch((error) => {
        if (active) handle(error);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [row.id, refresh, handle]);
  async function create(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const fields = new FormData(form);
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await api(`receivables/${row.id}/offers`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          advanceAmount: fields.get("advance"),
          currency: row.currency,
          discountRateBps: Number(fields.get("rate")),
          tenorDays: Number(fields.get("tenor")),
          expiresAt: new Date(fields.get("expiry")!.toString()).toISOString(),
        }),
      });
      setNotice(
        "Offer submitted. Only your institution and the exporter can see its terms.",
      );
      form.reset();
      setRefresh((v) => v + 1);
    } catch (error) {
      handle(error);
    } finally {
      setBusy(false);
    }
  }
  async function mutate(path: string) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await api(path, { method: "POST" });
      setReview(null);
      onChanged();
    } catch (error) {
      handle(error);
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="panel financing-panel">
      <div className="panel-heading">
        <div>
          <h2>Financing offers & agreement</h2>
          <p className="muted">
            Private terms. A single accepted offer locks this receivable to one
            institution.
          </p>
        </div>
        <button
          className="secondary"
          disabled={busy || loading}
          onClick={() => {
            setError("");
            setLoading(true);
            setRefresh((v) => v + 1);
          }}
        >
          Refresh offers
        </button>
      </div>
      {error && <ErrorNotice message={error} />}
      {notice && (
        <div className="success" role="status">
          {notice}
        </div>
      )}
      {loading ? (
        <p role="status">Loading financing terms…</p>
      ) : (
        data && (
          <>
            {data.can_offer && (
              <form className="offer-form" onSubmit={create}>
                <h3>Submit a financing offer</h3>
                <p className="muted">
                  Advance currency: {row.currency}. No currency conversion is
                  performed.
                </p>
                <fieldset disabled={busy}>
                  <div className="form-grid">
                    <label>
                      Advance amount ({row.currency})
                      <input
                        name="advance"
                        inputMode="decimal"
                        pattern="[0-9]+(\.[0-9]+)?"
                        required
                        maxLength={32}
                        placeholder="9750.00"
                      />
                    </label>
                    <label>
                      Discount rate (basis points)
                      <input
                        name="rate"
                        type="number"
                        min="0"
                        max="10000"
                        step="1"
                        defaultValue="250"
                        required
                      />
                    </label>
                    <label>
                      Tenor (days)
                      <input
                        name="tenor"
                        type="number"
                        min="1"
                        max="3650"
                        step="1"
                        defaultValue="60"
                        required
                      />
                    </label>
                    <label>
                      Offer expires (your local time)
                      <input
                        name="expiry"
                        type="datetime-local"
                        defaultValue={expiryDefault()}
                        required
                      />
                    </label>
                  </div>
                  <p className="muted">
                    100 basis points = 1%. The submitted advance is the agreed
                    amount; no payout or fee calculation is implied.
                  </p>
                  <button className="primary" disabled={busy}>
                    {busy ? "Submitting…" : "Submit offer"}
                  </button>
                </fieldset>
              </form>
            )}
            <div className="offer-list">
              {data.offers.length ? (
                data.offers.map((offer) => (
                  <article className="offer-card" key={offer.id}>
                    <div className="panel-heading">
                      <strong>{offer.financier_org_id}</strong>
                      <Status value={offer.status} />
                    </div>
                    <dl className="offer-facts">
                      <div>
                        <dt>Advance</dt>
                        <dd>{offerMoney(offer)}</dd>
                      </div>
                      <div>
                        <dt>Discount</dt>
                        <dd>
                          {(offer.discount_rate_bps / 100).toFixed(2)}% ·{" "}
                          {offer.discount_rate_bps} bps
                        </dd>
                      </div>
                      <div>
                        <dt>Tenor</dt>
                        <dd>{offer.tenor_days} days</dd>
                      </div>
                      <div>
                        <dt>Expires</dt>
                        <dd>
                          {new Date(offer.expires_at).toLocaleString("en-GB")}
                        </dd>
                      </div>
                    </dl>
                    {data.can_accept && offer.status === "OFFERED" && (
                      <div className="toolbar">
                        <button
                          className="primary"
                          disabled={busy}
                          onClick={() => setReview(offer)}
                        >
                          Review & accept
                        </button>
                        <button
                          className="secondary"
                          disabled={busy}
                          onClick={() => mutate(`offers/${offer.id}/reject`)}
                        >
                          Reject offer
                        </button>
                      </div>
                    )}
                  </article>
                ))
              ) : (
                <p className="muted">
                  {user.role === "ADMIN"
                    ? "Commercial offer terms are private to the exporter and offering institutions."
                    : row.status === "FINANCE_AVAILABLE"
                      ? "No offers to show yet."
                      : "Offers become available after this receivable is opened for financing."}
                </p>
              )}
            </div>
            {review && (
              <section
                className="acceptance-review"
                aria-label="Confirm financing terms"
              >
                <h3>Confirm acceptance</h3>
                <p>
                  Accept <strong>{offerMoney(review)}</strong> from{" "}
                  <strong>{review.financier_org_id}</strong> at{" "}
                  {(review.discount_rate_bps / 100).toFixed(2)}% for{" "}
                  {review.tenor_days} days.
                </p>
                <p>
                  This locks the receivable, records the agreement hash, and
                  rejects other active offers. It does not move funds or create
                  a legal assignment.
                </p>
                <div className="toolbar">
                  <button
                    className="primary"
                    disabled={busy}
                    onClick={() => mutate(`offers/${review.id}/accept`)}
                  >
                    {busy ? "Accepting…" : "Confirm acceptance"}
                  </button>
                  <button
                    className="secondary"
                    disabled={busy}
                    onClick={() => setReview(null)}
                  >
                    Cancel
                  </button>
                </div>
              </section>
            )}
            {data.agreement && (
              <section className="agreement">
                <h3>Recorded financing agreement</h3>
                <p className="muted">
                  The ledger records the consortium-recognized financing state
                  and a hash of the underlying agreement. Token state is not
                  legal ownership.
                </p>
                <dl>
                  <dt>Agreement SHA-256</dt>
                  <dd>
                    <code>{data.agreement.agreement_hash}</code>
                  </dd>
                  <dt>Lock transaction</dt>
                  <dd>
                    <code>{data.agreement.lock_transaction_id}</code>
                  </dd>
                </dl>
                <details>
                  <summary>View canonical agreement (TC-AGR-1)</summary>
                  <pre>{data.agreement.canonical_payload}</pre>
                </details>
              </section>
            )}
            {(data.can_disburse || data.payment) && (
              <section className="simulation">
                <h3>NPCI Payment Adapter — Sandbox Simulation</h3>
                <p>
                  No bank API is connected and no funds move. This records an
                  explicit mock advance and changes the receivable to FINANCED.
                </p>
                {data.payment ? (
                  <>
                    <Status value={data.payment.status} />
                    <code>{data.payment.transaction_id}</code>
                  </>
                ) : (
                  <button
                    className="primary"
                    disabled={busy}
                    onClick={() =>
                      mutate(`receivables/${row.id}/disbursement/mock`)
                    }
                  >
                    {busy ? "Recording simulation…" : "Simulate disbursement"}
                  </button>
                )}
              </section>
            )}
          </>
        )
      )}
    </section>
  );
}
