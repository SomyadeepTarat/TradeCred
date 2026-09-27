"use client";
import { useState, FormEvent } from "react";
import { useRouter } from "next/navigation";
import { api } from "../lib/api";
import { ErrorNotice } from "./workspace";

export function Login() {
  const router = useRouter();
  const [email, setEmail] = useState("exporter@tradecred.demo");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await api("auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      setPassword("");
      router.replace("/receivables");
    } catch (error) {
      setError(error instanceof Error ? error.message : "Sign in failed.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <main className="login-page">
      <section className="login-story">
        <div className="brand">
          <span className="brand-mark">T</span>TradeCred
        </div>
        <div>
          <p className="eyebrow">FROM INVOICE TO TRUSTED RECEIVABLE</p>
          <h1>
            A clearer view of
            <br />
            your trade.
          </h1>
          <p>
            One workspace to prepare invoices, track verification, and follow
            every recorded step.
          </p>
        </div>
        <p className="login-boundary">
          Permissioned receivables infrastructure.
          <br />
          Prototype · No live payment connection.
        </p>
      </section>
      <section className="login-form">
        <span className="small-tag">TRADECRED WORKSPACE</span>
        <h2>Welcome back</h2>
        <p className="muted">Sign in with your organization’s demo account.</p>
        <form onSubmit={submit}>
          {error && <ErrorNotice message={error} />}
          <label>
            Email address
            <input
              type="email"
              autoComplete="username"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </label>
          <label>
            Password
            <input
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </label>
          <button className="primary" disabled={busy}>
            {busy ? "Signing in…" : "Sign in →"}
          </button>
        </form>
        <div className="demo-identities">
          <p className="eyebrow">DEMO IDENTITIES</p>
          {["exporter", "admin", "bank", "nbfc", "settlement"].map((role) => (
            <button
              key={role}
              type="button"
              onClick={() => setEmail(`${role}@tradecred.demo`)}
            >
              {role}@tradecred.demo
            </button>
          ))}
          <p className="muted">
            Use the demo password configured during setup. Exporters create and
            register; administrators verify.
          </p>
        </div>
      </section>
    </main>
  );
}
