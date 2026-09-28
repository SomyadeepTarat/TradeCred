"use client";
import { FormEvent, useState } from "react";
import { api, Registry } from "../lib/api";
import { ErrorNotice, Status, useApiError } from "./workspace";

export function RegistryChecker() {
  const [result, setResult] = useState<
    (Registry & { fingerprint: string }) | null
  >(null);
  const [busy, setBusy] = useState(false);
  const { error, setError, handle } = useApiError();
  async function check(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setResult(null);
    const form = new FormData(event.currentTarget);
    try {
      const amount = Number(form.get("amountMinor"));
      if (!Number.isSafeInteger(amount) || amount <= 0)
        throw new Error("Enter a positive whole number of minor units.");
      setResult(
        await api("registry/check", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            exporterId: form.get("exporterId"),
            buyerId: form.get("buyerId"),
            invoiceNumber: form.get("invoiceNumber"),
            invoiceDate: form.get("invoiceDate"),
            currency: form.get("currency"),
            amountMinor: amount,
          }),
        }),
      );
    } catch (error) {
      handle(error);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <div className="page-heading">
        <div>
          <p className="eyebrow">PRE-FINANCING CHECK</p>
          <h1>Registry checker</h1>
          <p className="muted">
            Check an invoice’s shared financing state before making an offer.
          </p>
        </div>
      </div>
      <div className="detail-grid">
        <section className="panel">
          <h2>Invoice identity</h2>
          <p className="muted">
            Defaults match the fictional flagship invoice. EUR 10,800 =
            1,080,000 minor units.
          </p>
          <form onSubmit={check} className="demo-form">
            <label>
              Exporter organization
              <input
                name="exporterId"
                required
                maxLength={120}
                defaultValue="ORG_EXPORTER_ALPHA"
              />
            </label>
            <label>
              Buyer ID
              <input
                name="buyerId"
                required
                maxLength={120}
                defaultValue="BUYER-DE-001"
              />
            </label>
            <label>
              Invoice number
              <input
                name="invoiceNumber"
                required
                maxLength={120}
                defaultValue="EXP-2026-1042"
              />
            </label>
            <label>
              Invoice date
              <input
                name="invoiceDate"
                type="date"
                required
                defaultValue="2026-09-21"
              />
            </label>
            <label>
              Currency
              <input
                name="currency"
                required
                pattern="[A-Z]{3}"
                defaultValue="EUR"
              />
            </label>
            <label>
              Amount in minor units
              <input
                name="amountMinor"
                type="number"
                min="1"
                max="9007199254740991"
                step="1"
                required
                defaultValue="1080000"
              />
            </label>
            <button className="primary" disabled={busy}>
              {busy ? "Checking…" : "Check registry"}
            </button>
          </form>
        </section>
        <section className="panel" aria-live="polite">
          <h2>Registry result</h2>
          {error && <ErrorNotice message={error} />}
          {result ? (
            <>
              <div className={result.eligible ? "success" : "error"}>
                <strong>
                  {result.reason === "RECEIVABLE_ALREADY_FINANCED"
                    ? "Duplicate receivable already financed."
                    : result.reason === "RECEIVABLE_ALREADY_LOCKED"
                      ? "Receivable already locked."
                      : !result.exists
                        ? "No registered match"
                        : result.eligible
                          ? "Registered and open for financing"
                          : "Not open for financing"}
                </strong>
              </div>
              <p>
                Ledger:{" "}
                <strong>
                  {result.backend === "mock"
                    ? "Mock ledger · Local simulation"
                    : "Drunix"}
                </strong>
              </p>
              {result.status && <Status value={result.status} />}
              {result.assetId && <p className="mono">{result.assetId}</p>}
              <h3>Invoice fingerprint</h3>
              <code>{result.fingerprint}</code>
            </>
          ) : (
            !error && (
              <p className="muted">
                Submit invoice metadata to view the registry result.
              </p>
            )
          )}
          <p className="muted">
            A clear result is not credit approval and cannot rule out financing
            outside this network. No private invoice terms are returned.
          </p>
        </section>
      </div>
    </>
  );
}
