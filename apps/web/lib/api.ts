export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public code?: string,
  ) {
    super(message);
  }
}
export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api/backend/${path}`, {
    ...init,
    cache: "no-store",
  });
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new ApiError(
      response.status,
      data.error?.message ||
        (response.status === 422
          ? "Check the invoice fields, currency precision and dates, then try again."
          : "The request failed. Please try again."),
      data.error?.code,
    );
  }
  return response.json() as Promise<T>;
}
export type User = {
  id: string;
  display_name: string;
  organization_id: string;
  role: "EXPORTER" | "ADMIN" | "FINANCIER" | "SETTLEMENT_OPERATOR";
};
export type Receivable = {
  id: string;
  asset_id: string | null;
  exporter_org_id: string;
  invoice_number: string | null;
  buyer_id: string | null;
  invoice_date: string | null;
  due_date: string;
  currency: string;
  face_value: string | null;
  face_value_bucket: string;
  status: string;
  invoice_fingerprint: string | null;
  document_hash: string | null;
  owner_org_id: string | null;
  financing_agreement_hash: string | null;
  ebrc_status: string | null;
  created_at: string;
  updated_at: string;
};
export type Detail = Receivable & {
  document_available: boolean;
  available_actions: string[];
  ledger_backend: "mock" | "drunix";
};
export type Audit = {
  id: string;
  event_type: string;
  receivable_id: string;
  created_at: string;
  actor_org_id: string;
  metadata_json: Record<string, string>;
};
export type History = {
  events: Audit[];
  ledger: {
    transaction_id: string;
    revision: number;
    to_status: string;
    created_at: string;
    backend: string;
  }[];
};
export type Page = {
  items: Receivable[];
  total: number;
  summary: {
    total: number;
    available: number;
    financed: number;
    settled: number;
  };
  recent_activity: Audit[];
};
export type Registry = {
  exists: boolean;
  eligible: boolean;
  status?: string;
  assetId?: string;
  backend: string;
  reason?: string;
};
export const label = (value: string) =>
  value
    .toLowerCase()
    .replaceAll("_", " ")
    .replace(/^./, (c) => c.toUpperCase());
export const date = (value: string) =>
  new Date(
    value.length === 10 ? value + "T00:00:00" : value,
  ).toLocaleDateString("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
// Keep exact server decimal strings; never round 64-bit minor units through JS Number.
export function money(
  row: Pick<Receivable, "face_value" | "currency">,
): string {
  if (row.face_value === null) return "Private value";
  const [integer, fraction] = row.face_value.split(".");
  return `${row.currency} ${integer.replace(/\B(?=(\d{3})+(?!\d))/g, ",")}${fraction === undefined ? "" : "." + fraction}`;
}
