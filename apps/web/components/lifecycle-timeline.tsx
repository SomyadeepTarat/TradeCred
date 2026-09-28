import { History, label } from "../lib/api";
const steps = [
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
];
export function LifecycleTimeline({
  status,
  history,
}: {
  status: string;
  history: History | null;
}) {
  const reached = new Map<string, string>();
  history?.events.forEach((e) => {
    if (e.metadata_json.toStatus)
      reached.set(e.metadata_json.toStatus, e.created_at);
  });
  history?.ledger.forEach((e) => reached.set(e.to_status, e.created_at));
  return (
    <section className="panel">
      <h2>Receivable journey</h2>
      <p className="muted">
        Recorded steps are marked complete. e-BRC eligibility is a workflow
        status, not certificate issuance.
      </p>
      <ol className="journey">
        {steps.map((step) => (
          <li
            key={step}
            className={
              status === step
                ? "current"
                : reached.has(step)
                  ? "complete"
                  : "pending"
            }
            aria-current={status === step ? "step" : undefined}
          >
            <span aria-hidden="true">{reached.has(step) ? "✓" : "○"}</span>
            <strong>{label(step)}</strong>
            <small>
              {status === step
                ? "Current state"
                : reached.has(step)
                  ? new Date(reached.get(step)!).toLocaleDateString("en-GB")
                  : "Not recorded"}
            </small>
          </li>
        ))}
      </ol>
      {!steps.includes(status) && (
        <p>
          Current exception state: <strong>{label(status)}</strong>
        </p>
      )}
    </section>
  );
}
