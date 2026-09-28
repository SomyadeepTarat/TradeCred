"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";
import { api, ApiError, User } from "../lib/api";

const Session = createContext<User | null>(null);
export const useUser = () => useContext(Session)!;
export function ErrorNotice({ message }: { message: string }) {
  return (
    <div className="error" role="alert">
      {message}
    </div>
  );
}
export function Status({ value }: { value: string }) {
  return (
    <span className={`status status-${value.toLowerCase()}`}>
      {value === "FINANCE_AVAILABLE" ? "Available" : value.replaceAll("_", " ")}
    </span>
  );
}
export function Workspace({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const path = usePathname();
  const [user, setUser] = useState<User | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    api<User>("auth/me")
      .then((user) => {
        if (active) setUser(user);
      })
      .catch((error) => {
        if (!active) return;
        if (error instanceof ApiError && error.status === 401)
          router.replace("/login");
        else setError("Unable to load your session. Refresh to try again.");
      });
    return () => {
      active = false;
    };
  }, [router]);
  async function logout() {
    try {
      await api("auth/logout", { method: "POST" });
      router.replace("/login");
    } catch {
      setError("Sign out failed. Please try again.");
    }
  }
  return (
    <div className="workspace">
      <aside className="sidebar">
        <Link className="brand" href="/receivables">
          <span className="brand-mark">T</span>TradeCred
        </Link>
        <p className="sidebar-caption">RECEIVABLE TRUST INFRASTRUCTURE</p>
        <nav aria-label="Main navigation">
          <Link
            aria-current={path === "/receivables" ? "page" : undefined}
            href="/receivables"
          >
            ▦{" "}
            <span>
              {user?.role === "ADMIN"
                ? "Verification workspace"
                : user?.role === "FINANCIER"
                  ? "Financier workspace"
                  : "Receivables"}
            </span>
          </Link>
          {user?.role === "EXPORTER" && (
            <Link
              aria-current={path === "/receivables/new" ? "page" : undefined}
              href="/receivables/new"
            >
              ＋ <span>Create receivable</span>
            </Link>
          )}
          <Link
            href="/receivables/registry"
            aria-current={path === "/receivables/registry" ? "page" : undefined}
          >
            ⌕ <span>Registry checker</span>
          </Link>
          {user?.role === "SETTLEMENT_OPERATOR" && (
            <Link
              href="/receivables/settlement"
              aria-current={
                path === "/receivables/settlement" ? "page" : undefined
              }
            >
              ↗ <span>Settlement simulator</span>
            </Link>
          )}
          {user?.role === "ADMIN" && (
            <Link
              href="/receivables/audit"
              aria-current={path === "/receivables/audit" ? "page" : undefined}
            >
              ≡ <span>Audit & security</span>
            </Link>
          )}
        </nav>
        <div className="sidebar-bottom">
          <span className="small-tag">PROTOTYPE · SANDBOX</span>
          <p>
            Drunix is the target platform.
            <br />
            No live payment connection.
          </p>
        </div>
      </aside>
      <div className="workspace-main">
        <header className="topbar">
          <span>Trade finance workspace</span>
          {user && (
            <div className="account">
              <span>
                {user.display_name}
                <small>{user.role.replaceAll("_", " ")}</small>
              </span>
              <button className="text-button" onClick={logout}>
                Sign out
              </button>
            </div>
          )}
        </header>
        <main id="main-content">
          {error && <ErrorNotice message={error} />}
          {!user ? (
            <p role="status">Loading your workspace…</p>
          ) : (
            <Session.Provider value={user}>{children}</Session.Provider>
          )}
        </main>
        <footer>
          TradeCred is a prototype. It does not move funds, issue e-BRC
          certificates, or establish legal ownership through token state.
        </footer>
      </div>
    </div>
  );
}
export function useApiError() {
  const router = useRouter();
  const [error, setError] = useState("");
  const handle = useCallback(
    (error: unknown) => {
      if (error instanceof ApiError && error.status === 401) {
        router.replace("/login");
        return;
      }
      setError(
        error instanceof Error
          ? error.message
          : "The request failed. Please try again.",
      );
    },
    [router],
  );
  return { error, setError, handle };
}
