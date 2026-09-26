"use client";
import Link from "next/link";
import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "../lib/api";
import { ErrorNotice, useApiError, useUser } from "./workspace";

export function CreateReceivable() {
  const router = useRouter();
  const user = useUser();
  const [busy, setBusy] = useState(false);
  const { error, setError, handle } = useApiError();
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    const values = new FormData(event.currentTarget);
    const document = values.get("document") as File;
    if (!document?.size) {
      setError("Select an invoice PDF.");
      return;
    }
    if (
      values.get("dueDate")!.toString() < values.get("invoiceDate")!.toString()
    ) {
      setError("Due date must not precede invoice date.");
      return;
    }
    const metadata = Object.fromEntries(
      [
        "buyerId",
        "invoiceNumber",
        "invoiceDate",
        "currency",
        "amount",
        "dueDate",
      ].map((key) => [key, values.get(key)]),
    );
    const body = new FormData();
    body.set("metadata", JSON.stringify(metadata));
    body.set("document", document);
    setBusy(true);
    try {
      const result = await api<{ id: string }>("receivables", {
        method: "POST",
        body,
      });
      router.push(`/receivables/${result.id}`);
    } catch (error) {
      handle(error);
    } finally {
      setBusy(false);
    }
  }
  if (user.role !== "EXPORTER")
    return (
      <ErrorNotice message="Only exporters can create receivables. Use the register to review submitted invoices." />
    );
  return (
    <>
      <Link className="back-link" href="/receivables">
        ← Receivables
      </Link>
      <div className="page-heading">
        <div>
          <p className="eyebrow">NEW RECEIVABLE</p>
          <h1>Start with your invoice</h1>
          <p className="muted">
            Add the invoice details and original PDF to create a private draft.
          </p>
        </div>
      </div>
      <div className="form-layout">
        <form className="panel invoice-form" onSubmit={submit}>
          {error && <ErrorNotice message={error} />}
          <h2>Invoice details</h2>
          <p className="muted">Exporter: {user.organization_id}</p>
          <fieldset disabled={busy}>
            <div className="form-grid">
              <label>
                Buyer ID
                <input
                  name="buyerId"
                  maxLength={120}
                  required
                  placeholder="BUYER-DE-001"
                />
              </label>
              <label>
                Invoice number
                <input
                  name="invoiceNumber"
                  maxLength={120}
                  required
                  placeholder="EXP-2026-1042"
                />
              </label>
              <label>
                Invoice date
                <input name="invoiceDate" type="date" required />
              </label>
              <label>
                Due date
                <input name="dueDate" type="date" required />
              </label>
              <label>
                Currency
                <input
                  name="currency"
                  aria-label="Currency"
                  maxLength={3}
                  minLength={3}
                  pattern="[A-Za-z]{3}"
                  defaultValue="EUR"
                  required
                  aria-describedby="currency-help"
                />
                <small id="currency-help">
                  Three-letter ISO code, such as EUR or INR.
                </small>
              </label>
              <label>
                Face value
                <input
                  name="amount"
                  aria-label="Face value"
                  inputMode="decimal"
                  pattern="[0-9]+(\.[0-9]+)?"
                  maxLength={32}
                  required
                  placeholder="10800.00"
                />
                <small>
                  Exact invoice amount. Use a decimal point, without commas.
                </small>
              </label>
            </div>
            <div className="file-field">
              <label>
                Original invoice PDF
                <input
                  name="document"
                  type="file"
                  accept="application/pdf,.pdf"
                  required
                />
              </label>
              <p className="muted">
                Unencrypted PDF, 1–100 pages. Default upload limit: 10 MiB.
              </p>
            </div>
            <div className="form-actions">
              <Link href="/receivables" className="text-button">
                Cancel
              </Link>
              <button className="primary" disabled={busy}>
                {busy ? "Uploading invoice…" : "Create draft →"}
              </button>
            </div>
          </fieldset>
        </form>
        <aside className="guide">
          <span className="small-tag">WHAT HAPPENS NEXT</span>
          <h2>A traceable starting point.</h2>
          <ol>
            <li>
              <strong>Fingerprint generated</strong>
              <p>
                Your invoice identity is normalized and hashed, independently of
                the PDF.
              </p>
            </li>
            <li>
              <strong>Duplicate check</strong>
              <p>
                Existing local invoices are blocked. Your detail page checks the
                selected registry.
              </p>
            </li>
            <li>
              <strong>Ready for review</strong>
              <p>
                Submit the draft for administrator verification, then register
                the asset.
              </p>
            </li>
          </ol>
          <p className="muted">
            Your original PDF remains private. Only its integrity hash is
            recorded on the ledger.
          </p>
        </aside>
      </div>
    </>
  );
}
