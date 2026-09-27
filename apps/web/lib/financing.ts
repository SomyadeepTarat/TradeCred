export type Offer = {
  id: string;
  receivable_id: string;
  financier_org_id: string;
  advance_amount: string;
  currency: string;
  discount_rate_bps: number;
  tenor_days: number;
  expires_at: string;
  status: "OFFERED" | "ACCEPTED" | "REJECTED" | "EXPIRED";
  created_at: string;
};
export type Financing = {
  offers: Offer[];
  agreement: {
    id: string;
    offer_id: string;
    agreement_hash: string;
    canonical_payload: string;
    accepted_at: string;
    lock_transaction_id: string;
    financing_transaction_id: string | null;
  } | null;
  payment: {
    transaction_id: string;
    status: "SIMULATED_SUCCEEDED";
    backend: "mock";
  } | null;
  can_offer: boolean;
  can_accept: boolean;
  can_disburse: boolean;
  backend: "mock" | "drunix";
};
