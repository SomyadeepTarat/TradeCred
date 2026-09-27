"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { api, date, Page } from "../lib/api";
import { ErrorNotice, Status, useApiError } from "./workspace";

export function FinancierDashboard() {
  const [view, setView] = useState("available");
  const [offset, setOffset] = useState(0);
  const [refresh, setRefresh] = useState(0);
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState<Page | null>(null);
  const { error, setError, handle } = useApiError();
  useEffect(() => {
    let active = true;
    api<Page>(`receivables?view=${view}&limit=20&offset=${offset}`)
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
  }, [view, offset, refresh, handle]);
  return (
    <>
      <div className="page-heading">
        <div>
          <p className="eyebrow">INSTITUTIONAL FINANCING</p>
          <h1>Financier workspace</h1>
          <p className="muted">
            Discover open receivables, submit private offers, and track your
            financing.
          </p>
        </div>
        <button
          className="secondary"
          disabled={loading}
          onClick={() => {
            setError("");
            setLoading(true);
            setRefresh((v) => v + 1);
          }}
        >
          Refresh
        </button>
      </div>
      <div className="ledger-banner">
        <strong>Permissioned registry</strong>
        <span>
          Invoice documents and exact face values remain private to exporters.
        </span>
      </div>
      <div className="view-tabs" role="group" aria-label="Financing views">
        {[
          ["available", "Available receivables"],
          ["offers", "My offers"],
          ["assigned", "Assigned to us"],
        ].map(([value, title]) => (
          <button
            key={value}
            aria-pressed={view === value}
            onClick={() => {
              setView(value);
              setOffset(0);
              setLoading(true);
              setError("");
              setRefresh((v) => v + 1);
            }}
          >
            {title}
          </button>
        ))}
      </div>
      {error && <ErrorNotice message={error} />}
      <section className="panel">
        <div className="panel-heading">
          <h2>
            {view === "available"
              ? "Open for financing"
              : view === "offers"
                ? "Receivables with our offers"
                : "Our financing portfolio"}
          </h2>
          <span className="muted">
            {data && !loading ? `${data.total} receivables` : "Loading…"}
          </span>
        </div>
        {loading ? (
          <p role="status" className="empty">
            Loading financing records…
          </p>
        ) : error ? (
          <p>Records are unavailable. Refresh to retry.</p>
        ) : data?.items.length ? (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Asset</th>
                  <th>Exporter organization</th>
                  <th>Value range</th>
                  <th>Due date</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((row) => (
                  <tr key={row.id}>
                    <td>
                      <Link
                        className="invoice-link mono"
                        href={`/receivables/${row.id}`}
                      >
                        {row.asset_id}
                      </Link>
                    </td>
                    <td>{row.exporter_org_id}</td>
                    <td>
                      {row.currency} {row.face_value_bucket}
                    </td>
                    <td>{date(row.due_date)}</td>
                    <td>
                      <Status value={row.status} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="empty">
            <h3>No receivables in this view</h3>
            <p>
              {view === "available"
                ? "Receivables appear after the exporter opens them for financing."
                : "Your offers and accepted assignments will appear here."}
            </p>
          </div>
        )}
        {data && data.total > 20 && (
          <div className="pagination">
            <span>
              {offset + 1}–{Math.min(offset + 20, data.total)} of {data.total}
            </span>
            <button
              disabled={loading || offset === 0}
              onClick={() => {
                setOffset(offset - 20);
                setLoading(true);
              }}
            >
              Previous
            </button>
            <button
              disabled={loading || offset + 20 >= data.total}
              onClick={() => {
                setOffset(offset + 20);
                setLoading(true);
              }}
            >
              Next
            </button>
          </div>
        )}
      </section>
      <p className="muted">
        A registry check is required before each financing action. Financing
        locks prevent a second institution from financing the same registered
        receivable inside this network.
      </p>
    </>
  );
}
