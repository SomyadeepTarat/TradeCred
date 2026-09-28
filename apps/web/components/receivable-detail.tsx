"use client";
import Link from "next/link";
import { FinancingPanel } from "./financing-panel";
import { useEffect, useState } from "react";
import { api, date, Detail, History, label, money, Registry } from "../lib/api";
import { ErrorNotice, Status, useApiError, useUser } from "./workspace";

const actionLabels: Record<string, string> = {
  submit: "Submit for verification",
  verify: "Verify invoice integrity",
  register: "Register receivable",
  "open-financing": "Open for financing",
};
const guidance: Record<string, string> = {
  DRAFT: "Review the invoice details, then submit this draft for verification.",
  SUBMITTED:
    "Awaiting administrator verification. An administrator must sign in to complete the review.",
  VERIFIED:
    "Verification is recorded. You can now register this receivable on the selected ledger.",
  REGISTERED:
    "Registration is recorded. Open the receivable for future financing workflows when ready.",
  LOCKED:
    "An offer is accepted and this receivable is locked. The assigned institution can record a simulated disbursement.",
  FINANCED:
    "Financing is recorded with an explicit sandbox payout. Awaiting an authenticated bank settlement event.",
  PAYMENT_CONFIRMED:
    "Inward payment confirmed by an authenticated bank event. No funds are moved by TradeCred.",
  FINANCE_AVAILABLE:
    "This receivable is open for financing. Institutions can submit offers; the exporter can accept one.",
};
export function ReceivableDetail({ id }: { id: string }) {
  const user = useUser();
  const [row, setRow] = useState<Detail | null>(null);
  const [history, setHistory] = useState<History | null>(null);
  const [registry, setRegistry] = useState<Registry | null>(null);
  const [registryError, setRegistryError] = useState("");
  const [historyError, setHistoryError] = useState("");
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [refresh, setRefresh] = useState(0);
  const [notice, setNotice] = useState("");
  const { error, setError, handle } = useApiError();
  useEffect(() => {
    let active = true;
    api<Detail>(`receivables/${id}`)
      .then(async (detail) => {
        if (!active) return;
        setRow(detail);
        const results = await Promise.allSettled([
          api<History>(`receivables/${id}/history`),
          detail.invoice_fingerprint
            ? api<Registry>(
                `registry/fingerprint/${detail.invoice_fingerprint}`,
              )
            : Promise.resolve(null),
        ]);
        if (!active) return;
        if (results[0].status === "fulfilled") {
          setHistory(results[0].value);
          setHistoryError("");
        } else {
          setHistory(null);
          setHistoryError("History could not be loaded. Refresh to retry.");
          handle(results[0].reason);
        }
        if (results[1].status === "fulfilled") {
          setRegistry(results[1].value);
          setRegistryError("");
        } else {
          setRegistry(null);
          setRegistryError(
            "Registry unavailable. Duplicate status is unknown; refresh to retry.",
          );
        }
      })
      .catch((error) => {
        if (active) {
          setRow(null);
          handle(error);
        }
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [id, refresh, handle]);
  function reload() {
    setError("");
    setLoading(true);
    setRefresh((value) => value + 1);
  }
  async function advance(action: string) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await api(`receivables/${id}/${action}`, { method: "POST" });
      setNotice(`${actionLabels[action]} completed.`);
      reload();
    } catch (error) {
      handle(error);
    } finally {
      setBusy(false);
    }
  }
  async function integrity() {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const result = await api<{ verified: boolean }>(
        `receivables/${id}/document/integrity`,
      );
      if (result.verified)
        setNotice(
          "Document integrity verified. The stored PDF matches its recorded hash.",
        );
      else
        setError(
          "Document integrity failed. The stored PDF does not match its recorded hash.",
        );
    } catch (error) {
      handle(error);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <Link className="back-link" href="/receivables">
        ← Receivables
      </Link>
      {error && <ErrorNotice message={error} />}
      {notice && (
        <div className="success" role="status">
          {notice}
        </div>
      )}
      {loading ? (
        <p className="empty" role="status">
          Loading receivable and recorded history…
        </p>
      ) : row ? (
        <>
          <div className="page-heading">
            <div>
              <p className="eyebrow">RECEIVABLE DETAIL</p>
              <h1>{row.invoice_number || row.asset_id || "Invoice review"}</h1>
              <p className="muted mono">
                {row.asset_id || `Draft · ${row.id}`}
              </p>
            </div>
            <div className="detail-heading-actions">
              <Status value={row.status} />
              <button className="secondary" onClick={reload} disabled={busy}>
                Refresh
              </button>
            </div>
          </div>
          <div className="ledger-banner">
            <span className="ledger-dot" />
            <strong>
              {row.ledger_backend === "mock"
                ? "Mock ledger · Local simulation"
                : "Drunix · Configured gateway"}
            </strong>
            <span>
              {row.ledger_backend === "mock"
                ? "Recorded transactions use MOCK- identifiers."
                : "Ledger writes require confirmed commits. Availability is checked per request."}
            </span>
          </div>
          <section className="action-panel">
            <div>
              <h2>
                {row.status === "SUBMITTED" && user.role === "ADMIN"
                  ? "Ready for administrator review"
                  : "Next step"}
              </h2>
              <p>
                {guidance[row.status] || "Review the recorded lifecycle below."}
              </p>
              {!row.document_hash && (
                <p>
                  A stored invoice PDF is required before this record can
                  advance.
                </p>
              )}
            </div>
            <div>
              {row.available_actions.map((action) => (
                <button
                  className="primary"
                  key={action}
                  disabled={busy || loading}
                  onClick={() => advance(action)}
                >
                  {busy ? "Processing…" : actionLabels[action]}
                </button>
              ))}
            </div>
          </section>
          <div className="detail-grid">
            <section className="panel">
              <h2>Invoice overview</h2>
              <dl className="facts">
                <div>
                  <dt>
                    {user.role === "FINANCIER" ? "Value range" : "Face value"}
                  </dt>
                  <dd className="value-large">
                    {user.role === "FINANCIER"
                      ? `${row.currency} ${row.face_value_bucket}`
                      : money(row)}
                  </dd>
                </div>
                <div>
                  <dt>Buyer ID</dt>
                  <dd>{row.buyer_id || "Private to exporter"}</dd>
                </div>
                <div>
                  <dt>Invoice date</dt>
                  <dd>
                    {row.invoice_date
                      ? date(row.invoice_date)
                      : "Private to exporter"}
                  </dd>
                </div>
                <div>
                  <dt>Due date</dt>
                  <dd>{date(row.due_date)}</dd>
                </div>
                <div>
                  <dt>Exporter organization</dt>
                  <dd>{row.exporter_org_id}</dd>
                </div>
                <div>
                  <dt>Financing institution</dt>
                  <dd>{row.owner_org_id || "None assigned"}</dd>
                </div>
              </dl>
            </section>
            <section className="panel">
              <h2>Registry check</h2>
              {registryError ? (
                <ErrorNotice message={registryError} />
              ) : registry ? (
                <>
                  <div className="registry-result">
                    <span className="status">
                      {!registry.exists
                        ? "No registered match"
                        : registry.assetId === row.asset_id
                          ? "This asset is registered"
                          : "Duplicate registered asset"}
                    </span>
                    <p>
                      {!registry.exists
                        ? "No matching fingerprint was found in the selected registry. This does not rule out off-network financing."
                        : registry.assetId === row.asset_id
                          ? "The fingerprint resolves to this receivable’s registered asset."
                          : "This fingerprint is already associated with another asset. Registration will be blocked."}
                    </p>
                  </div>
                  {registry.status && (
                    <p>
                      Registry status: <Status value={registry.status} />
                    </p>
                  )}
                  {registry.assetId && (
                    <p className="mono">{registry.assetId}</p>
                  )}
                  <p className="muted">
                    Eligibility is a registry status, not credit approval.
                  </p>
                </>
              ) : (
                <p className="muted">
                  A fingerprint is required for a registry check.
                </p>
              )}
            </section>
          </div>
          <section className="panel">
            <div className="panel-heading">
              <div>
                <h2>Document & invoice identity</h2>
                <p className="muted">
                  The business fingerprint identifies the invoice. The document
                  hash verifies the original PDF.
                </p>
              </div>
              {row.document_available && (
                <div className="toolbar">
                  <button
                    className="secondary"
                    disabled={busy}
                    onClick={integrity}
                  >
                    Check PDF integrity
                  </button>
                  <a
                    className="secondary"
                    href={`/api/backend/receivables/${id}/document`}
                    download
                  >
                    Download PDF ↓
                  </a>
                </div>
              )}
            </div>
            <div className="hash-grid">
              <div>
                <h3>
                  Invoice fingerprint <span className="small-tag">TC-FP-1</span>
                </h3>
                <code>{row.invoice_fingerprint || "Not generated"}</code>
              </div>
              <div>
                <h3>Document SHA-256</h3>
                <code>{row.document_hash || "No document recorded"}</code>
              </div>
            </div>
          </section>
          <FinancingPanel row={row} onChanged={reload} />
          <div className="detail-grid">
            <section className="panel">
              <h2>Lifecycle history</h2>
              {historyError && <ErrorNotice message={historyError} />}
              {history?.events.length ? (
                <ol className="timeline">
                  {history.events.map((event) => (
                    <li key={event.id}>
                      <span className="timeline-point" />
                      <div>
                        <strong>{label(event.event_type)}</strong>
                        <p>
                          {event.metadata_json.toStatus
                            ? label(event.metadata_json.toStatus)
                            : "Recorded event"}{" "}
                          · {event.actor_org_id}
                        </p>
                        <time>
                          {new Date(event.created_at).toLocaleString("en-GB")}
                        </time>
                      </div>
                    </li>
                  ))}
                </ol>
              ) : (
                !historyError && (
                  <p className="muted">
                    No recorded application history for this receivable.
                  </p>
                )
              )}
            </section>
            <div>
              <section className="panel">
                <h2>Ledger transactions</h2>
                {history?.ledger.length ? (
                  <ul className="transaction-list">
                    {history.ledger.map((tx) => (
                      <li key={tx.transaction_id}>
                        <div>
                          <Status value={tx.to_status} />
                          <span className="muted">
                            Revision {tx.revision} · {tx.backend}
                          </span>
                        </div>
                        <code>{tx.transaction_id}</code>
                        <small>{date(tx.created_at)}</small>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="muted">
                    {historyError
                      ? "Ledger history unavailable."
                      : "No ledger transactions recorded yet."}
                  </p>
                )}
              </section>
              <section className="panel">
                <h2>Settlement status</h2>
                <p>
                  {row.status === "PAYMENT_CONFIRMED"
                    ? "Inward payment confirmed. Remittance reference linked."
                    : "Awaiting a verified signed bank settlement event."}
                </p>
                <p className="muted">
                  {row.ebrc_status
                    ? `e-BRC workflow status: ${row.ebrc_status}`
                    : "No e-BRC workflow status recorded."}{" "}
                  TradeCred does not issue e-BRC certificates.
                </p>
              </section>
            </div>
          </div>
        </>
      ) : (
        !loading && (
          <div className="empty">
            <h1>Receivable unavailable</h1>
            <p>
              The record could not be loaded or is outside your organization.
            </p>
            <button className="secondary" onClick={reload}>
              Try again
            </button>
          </div>
        )
      )}
    </>
  );
}
