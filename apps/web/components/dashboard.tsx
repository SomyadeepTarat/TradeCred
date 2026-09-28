"use client";
import { SettlementSimulator } from "./settlement-simulator";
import Link from "next/link";
import { FinancierDashboard } from "./financier-dashboard";
import { useEffect, useState } from "react";
import { api, date, label, money, Page } from "../lib/api";
import { ErrorNotice, Status, useApiError, useUser } from "./workspace";

function ExporterDashboard() {
  const user = useUser();
  const [data, setData] = useState<Page | null>(null);
  const [status, setStatus] = useState("");
  const [offset, setOffset] = useState(0);
  const [refresh, setRefresh] = useState(0);
  const [loading, setLoading] = useState(true);
  const { error, setError, handle } = useApiError();
  useEffect(() => {
    if (user.role !== "EXPORTER" && user.role !== "ADMIN") return;
    let active = true;
    api<Page>(
      `receivables?limit=20&offset=${offset}${status ? `&status=${status}` : ""}`,
    )
      .then((data) => {
        if (active) setData(data);
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
  }, [status, offset, refresh, user.role, handle]);
  function reload() {
    setError("");
    setLoading(true);
    setRefresh((r) => r + 1);
  }
  if (user.role !== "EXPORTER" && user.role !== "ADMIN")
    return (
      <section className="empty">
        <h1>Your account is connected</h1>
        <p>Use the navigation to open the workspace available to your role.</p>
      </section>
    );
  return (
    <>
      <div className="page-heading">
        <div>
          <p className="eyebrow">
            {user.role === "ADMIN"
              ? "CONSORTIUM VERIFICATION"
              : "EXPORTER OVERVIEW"}
          </p>
          <h1>
            {user.role === "ADMIN"
              ? "Verification workspace"
              : "Your receivables"}
          </h1>
          <p className="muted">
            {user.role === "ADMIN"
              ? "Review submitted records and confirm invoice integrity."
              : "Prepare, register, and track your trade invoices in one place."}
          </p>
        </div>
        {user.role === "EXPORTER" && (
          <Link className="primary" href="/receivables/new">
            ＋ Create receivable
          </Link>
        )}
      </div>
      {error && <ErrorNotice message={error} />}
      <div className="metrics">
        {(
          [
            ["total", "Total receivables"],
            ["available", "Available for finance"],
            ["financed", "Financed · outstanding"],
            ["settled", "Payment confirmed"],
          ] as const
        ).map(([key, title]) => (
          <div className="metric" key={key}>
            <span>{title}</span>
            <strong>{data?.summary[key] ?? "—"}</strong>
            <small>
              {key === "total"
                ? "Across all statuses"
                : key === "settled"
                  ? "Including realized and closed"
                  : key === "financed"
                    ? "Including overdue and disputed"
                    : "Registered and open"}
            </small>
          </div>
        ))}
      </div>
      <section className="panel">
        <div className="panel-heading">
          <h2>Receivable register</h2>
          <div className="toolbar">
            <label className="filter">
              Status
              <select
                aria-label="Filter by status"
                value={status}
                onChange={(e) => {
                  setStatus(e.target.value);
                  setOffset(0);
                  setLoading(true);
                  setError("");
                }}
              >
                {[
                  "",
                  "DRAFT",
                  "SUBMITTED",
                  "VERIFIED",
                  "REGISTERED",
                  "FINANCE_AVAILABLE",
                  "LOCKED",
                  "FINANCED",
                  "PAYMENT_CONFIRMED",
                  "REALIZED",
                  "EBRC_ELIGIBLE",
                  "CLOSED",
                  "REJECTED_DUPLICATE",
                  "RELEASED",
                  "OVERDUE",
                  "DISPUTED",
                ].map((s) => (
                  <option key={s} value={s}>
                    {s ? label(s) : "All statuses"}
                  </option>
                ))}
              </select>
            </label>
            <button className="secondary" disabled={loading} onClick={reload}>
              Refresh
            </button>
          </div>
        </div>
        {loading ? (
          <p className="empty" role="status">
            Loading receivables…
          </p>
        ) : error ? (
          <p className="empty">
            Could not refresh the register. Use Refresh to try again.
          </p>
        ) : data?.items.length ? (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Invoice / Asset</th>
                  <th>{user.role === "ADMIN" ? "Exporter" : "Buyer"}</th>
                  <th>Face value</th>
                  <th>Due date</th>
                  <th>Status</th>
                  <th>
                    <span className="sr-only">Open</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((row) => (
                  <tr key={row.id}>
                    <td>
                      <Link
                        className="invoice-link"
                        href={`/receivables/${row.id}`}
                      >
                        {row.invoice_number ||
                          row.asset_id ||
                          row.id.slice(0, 8)}
                      </Link>
                      <small>
                        {row.asset_id ? "Registered asset" : "Not registered"}
                      </small>
                    </td>
                    <td>{row.buyer_id || row.exporter_org_id}</td>
                    <td className="amount">{money(row)}</td>
                    <td>{date(row.due_date)}</td>
                    <td>
                      <Status value={row.status} />
                    </td>
                    <td>
                      <Link
                        aria-label={`View ${row.invoice_number || row.id}`}
                        href={`/receivables/${row.id}`}
                      >
                        ↗
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="empty">
            <div className="empty-icon">▤</div>
            <h3>
              {status ? "No matching receivables" : "Your register starts here"}
            </h3>
            <p>
              {status
                ? "Choose another status to see more records."
                : "Create your first receivable by uploading an invoice PDF."}
            </p>
            {user.role === "EXPORTER" && !status && (
              <Link className="secondary" href="/receivables/new">
                Create a receivable
              </Link>
            )}
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
      <section className="panel activity">
        <div className="panel-heading">
          <h2>Recent activity</h2>
          <span className="muted">Latest recorded events</span>
        </div>
        {data?.recent_activity.length ? (
          <ul>
            {data.recent_activity.map((event) => (
              <li key={event.id}>
                <span className="activity-dot" />
                <div>
                  <Link href={`/receivables/${event.receivable_id}`}>
                    {label(event.event_type)}
                  </Link>
                  <small>{event.actor_org_id}</small>
                </div>
                <time>{date(event.created_at)}</time>
              </li>
            ))}
          </ul>
        ) : (
          <p className="muted">
            Recorded activity will appear here as receivables progress.
          </p>
        )}
      </section>
    </>
  );
}

export function Dashboard() {
  const user = useUser();
  if (user.role === "SETTLEMENT_OPERATOR") return <SettlementSimulator />;
  return user.role === "FINANCIER" ? (
    <FinancierDashboard />
  ) : (
    <ExporterDashboard />
  );
}
