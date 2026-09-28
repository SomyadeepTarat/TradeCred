"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { api, Audit, label } from "../lib/api";
import { ErrorNotice, useApiError, useUser } from "./workspace";
type Security = {
  id: string;
  event_type: string;
  reason: string;
  request_id: string;
  created_at: string;
};
export function AuditDashboard() {
  const user = useUser();
  const [events, setEvents] = useState<Audit[]>([]);
  const [security, setSecurity] = useState<Security[]>([]);
  const [offset, setOffset] = useState(0);
  const [refresh, setRefresh] = useState(0);
  const [loading, setLoading] = useState(true);
  const { error, setError, handle } = useApiError();
  useEffect(() => {
    if (user.role !== "ADMIN") return;
    let active = true;
    Promise.all([
      api<Audit[]>(`audit/events?limit=50&offset=${offset}`),
      api<Security[]>(`audit/security-events?limit=50&offset=${offset}`),
    ])
      .then(([a, s]) => {
        if (active) {
          setEvents(a);
          setSecurity(s);
        }
      })
      .catch((e) => {
        if (active) handle(e);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [offset, refresh, user.role, handle]);
  if (user.role !== "ADMIN")
    return (
      <ErrorNotice message="Administrator access is required to inspect audit events." />
    );
  return (
    <>
      <div className="page-heading">
        <div>
          <p className="eyebrow">CONSORTIUM OVERSIGHT</p>
          <h1>Audit & security</h1>
          <p className="muted">
            Recorded participant activity, duplicate attempts and webhook
            rejections.
          </p>
        </div>
        <button
          className="secondary"
          onClick={() => {
            setError("");
            setLoading(true);
            setRefresh((v) => v + 1);
          }}
        >
          Refresh audit
        </button>
      </div>
      {error && <ErrorNotice message={error} />}
      {loading ? (
        <p role="status">Loading audit events…</p>
      ) : (
        <>
          <div className="detail-grid audit-feeds">
            <section className="panel">
              <h2>Security events</h2>
              {!security.length && <p>No security events on this page.</p>}
              <ol className="timeline">
                {security.map((e) => (
                  <li key={e.id}>
                    <span className="timeline-point" />
                    <div>
                      <strong>{label(e.event_type)}</strong>
                      <p>{e.reason}</p>
                      <small>
                        {new Date(e.created_at).toLocaleString("en-GB")}
                      </small>
                      <code>Request {e.request_id}</code>
                    </div>
                  </li>
                ))}
              </ol>
            </section>
            <section className="panel">
              <h2>Participant activity</h2>
              {!events.length && <p>No activity on this page.</p>}
              <ol className="timeline">
                {events.map((e) => (
                  <li key={e.id}>
                    <span className="timeline-point" />
                    <div>
                      <strong>{label(e.event_type)}</strong>
                      <p>{e.actor_org_id}</p>
                      <small>
                        {new Date(e.created_at).toLocaleString("en-GB")}
                      </small>
                      {e.metadata_json.toStatus && (
                        <p>{label(e.metadata_json.toStatus)}</p>
                      )}
                      {e.metadata_json.transactionId && (
                        <code>{e.metadata_json.transactionId}</code>
                      )}
                      {e.receivable_id && (
                        <Link href={`/receivables/${e.receivable_id}`}>
                          View receivable →
                        </Link>
                      )}
                    </div>
                  </li>
                ))}
              </ol>
            </section>
          </div>
        </>
      )}
      <div className="toolbar">
        <button
          className="secondary"
          disabled={loading || offset === 0}
          onClick={() => {
            setLoading(true);
            setOffset((v) => v - 50);
          }}
        >
          Previous
        </button>
        <span>
          Events {offset + 1}–{offset + 50} in each feed
        </span>
        <button
          className="secondary"
          disabled={loading || (events.length < 50 && security.length < 50)}
          onClick={() => {
            setLoading(true);
            setOffset((v) => v + 50);
          }}
        >
          Next
        </button>
      </div>
    </>
  );
}
