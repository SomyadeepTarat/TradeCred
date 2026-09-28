"use client";
import { useCallback, useEffect, useState } from "react";
import { api } from "../lib/api";
import { ErrorNotice, Status, useApiError, useUser } from "./workspace";

type Asset = { asset_id: string; currency: string; status: string };
type Result = {
  id: string;
  accepted: boolean;
  uncertain: boolean;
  code: string;
  event_id: string;
  asset_id: string;
  transaction_id: string | null;
  backend: string | null;
};
export function SettlementSimulator() {
  const user = useUser();
  const [assets, setAssets] = useState<Asset[]>([]);
  const [asset, setAsset] = useState("");
  const [amount, setAmount] = useState("1080000");
  const [currency, setCurrency] = useState("EUR");
  const [reference, setReference] = useState("IRM-DEMO-938291");
  const [result, setResult] = useState<Result | null>(null);
  const [saved, setSaved] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const { error, setError, handle } = useApiError();
  const load = useCallback(async () => {
    try {
      setAssets(await api<Asset[]>("simulator/assets"));
    } catch (error) {
      handle(error);
    } finally {
      setLoading(false);
    }
  }, [handle]);
  useEffect(() => {
    if (user.role !== "SETTLEMENT_OPERATOR") return;
    let active = true;
    api<Asset[]>("simulator/assets")
      .then((data) => {
        if (active) setAssets(data);
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
  }, [user.role, handle]);
  async function send(mode: "valid" | "invalid" | "replay") {
    setBusy(true);
    setError("");
    setResult(null);
    try {
      const minor = Number(amount);
      if (
        mode !== "replay" &&
        (!asset || !Number.isSafeInteger(minor) || minor <= 0)
      )
        throw new Error(
          "Select an asset and enter a positive whole amount in minor units.",
        );
      const data = await api<Result>(
        mode === "replay"
          ? `simulator/events/${saved}/replay`
          : "simulator/events",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          ...(mode !== "replay"
            ? {
                body: JSON.stringify({
                  asset_id: asset,
                  amount_minor: minor,
                  currency,
                  reference,
                  mode,
                }),
              }
            : {}),
        },
      );
      setResult(data);
      setSaved(data.id);
      await load();
    } catch (error) {
      handle(error);
    } finally {
      setBusy(false);
    }
  }
  if (user.role !== "SETTLEMENT_OPERATOR")
    return (
      <ErrorNotice message="Only settlement operators can use the sandbox simulator." />
    );
  return (
    <>
      <div className="page-heading">
        <div>
          <p className="eyebrow">AUTHORIZED BANK · SANDBOX</p>
          <h1>Settlement simulator</h1>
          <p className="muted">
            Submit an authenticated confirmation. No funds move.
          </p>
        </div>
        <button className="secondary" onClick={load} disabled={busy}>
          Refresh assets
        </button>
      </div>
      <div className="ledger-banner">
        <strong>Sandbox bank signing service</strong>
        <span>
          Real Ed25519 signature verification. The private key stays outside the
          browser and API.
        </span>
      </div>
      {error && <ErrorNotice message={error} />}
      <div className="detail-grid">
        <section className="panel">
          <h2>Payment confirmation</h2>
          {loading ? (
            <p role="status">Loading assets…</p>
          ) : (
            !assets.length && (
              <p>No financed assets available. Finance an invoice first.</p>
            )
          )}
          <div className="demo-form">
            <label>
              Asset
              <select
                aria-label="Asset"
                value={asset}
                onChange={(e) => {
                  setAsset(e.target.value);
                  setCurrency(
                    assets.find((a) => a.asset_id === e.target.value)
                      ?.currency || "EUR",
                  );
                  setResult(null);
                }}
              >
                <option value="">Select an asset</option>
                {assets.map((a) => (
                  <option key={a.asset_id} value={a.asset_id}>
                    {a.asset_id} · {a.status}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Amount in minor units
              <input
                type="number"
                min="1"
                step="1"
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
              />
            </label>
            <label>
              Currency
              <input
                value={currency}
                maxLength={3}
                onChange={(e) => setCurrency(e.target.value.toUpperCase())}
              />
            </label>
            <label>
              Remittance reference
              <input
                value={reference}
                maxLength={160}
                onChange={(e) => setReference(e.target.value)}
              />
            </label>
            <p className="muted">
              Flagship invoice: EUR 10,800 = 1,080,000 minor units. Confirmation
              must match the full invoice value, not its financing advance.
            </p>
            <div className="toolbar">
              <button
                className="primary"
                disabled={busy || !asset}
                onClick={() => send("valid")}
              >
                Send Valid Signed Event
              </button>
              <button
                className="secondary"
                disabled={busy || !asset}
                onClick={() => send("invalid")}
              >
                Send Invalid Signature
              </button>
              <button
                className="secondary"
                disabled={busy || !saved}
                onClick={() => send("replay")}
              >
                Replay Event
              </button>
            </div>
          </div>
        </section>
        <section className="panel" aria-live="polite">
          <h2>Verification result</h2>
          {busy ? (
            <p role="status">Verifying event…</p>
          ) : result ? (
            <>
              <Status
                value={
                  result.accepted
                    ? "PAYMENT_CONFIRMED"
                    : result.code === "INVALID_PAYMENT_SIGNATURE"
                      ? "SIGNATURE_REJECTED"
                      : result.code
                }
              />
              <p>
                {result.accepted
                  ? "Inward payment confirmed. Remittance reference linked."
                  : result.uncertain
                    ? "Outcome unknown. Restore availability, then use Replay Event to recover this exact event."
                    : "Event rejected. This attempt made no ledger state change."}
              </p>
              <p className="mono">{result.event_id}</p>
              {result.transaction_id && (
                <>
                  <p>Ledger: {result.backend}</p>
                  <code>{result.transaction_id}</code>
                </>
              )}
            </>
          ) : (
            <p className="muted">
              Send an event to inspect its verification result. Replay resubmits
              the exact most recent event, including its original signature and
              timestamp.
            </p>
          )}
        </section>
      </div>
    </>
  );
}
