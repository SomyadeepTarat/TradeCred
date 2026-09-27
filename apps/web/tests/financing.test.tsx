import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { api, ApiError, Detail } from "../lib/api";
import { FinancingPanel } from "../components/financing-panel";
import { FinancierDashboard } from "../components/financier-dashboard";
import { Financing } from "../lib/financing";
const { user, router } = vi.hoisted(() => ({
  user: { role: "EXPORTER" },
  router: { replace: vi.fn() },
}));
vi.mock("next/navigation", () => ({ useRouter: () => router }));
vi.mock("../lib/api", async (original) => ({
  ...(await original<typeof import("../lib/api")>()),
  api: vi.fn(),
}));
vi.mock("../components/workspace", async (original) => ({
  ...(await original<typeof import("../components/workspace")>()),
  useUser: () => user,
}));
const call = vi.mocked(api);
const row = {
  id: "record-1",
  currency: "EUR",
  status: "FINANCE_AVAILABLE",
} as Detail;
const offer = {
  id: "offer-1",
  receivable_id: "record-1",
  financier_org_id: "BANK-1",
  advance_amount: "9750.00",
  currency: "EUR",
  discount_rate_bps: 250,
  tenor_days: 60,
  expires_at: "2099-01-01T00:00:00Z",
  status: "OFFERED" as const,
  created_at: "2026-09-26T00:00:00Z",
};
const base: Financing = {
  offers: [offer],
  agreement: null,
  payment: null,
  can_offer: false,
  can_accept: true,
  can_disburse: false,
  backend: "mock",
};
beforeEach(() => {
  vi.clearAllMocks();
  user.role = "EXPORTER";
});
afterEach(cleanup);
test("acceptance requires review and confirms the selected offer once", async () => {
  call.mockResolvedValue(base);
  const changed = vi.fn();
  render(<FinancingPanel row={row} onChanged={changed} />);
  fireEvent.click(
    await screen.findByRole("button", { name: "Review & accept" }),
  );
  expect(call).toHaveBeenCalledTimes(1);
  expect(
    screen.getByRole("region", { name: "Confirm financing terms" }),
  ).toHaveTextContent("EUR 9,750.00");
  fireEvent.click(screen.getByRole("button", { name: "Confirm acceptance" }));
  await waitFor(() =>
    expect(call).toHaveBeenCalledWith("offers/offer-1/accept", {
      method: "POST",
    }),
  );
  expect(changed).toHaveBeenCalledTimes(1);
});
test("failed competing acceptance does not advance the detail view", async () => {
  call.mockImplementation(async (_, init) => {
    if (init) throw new ApiError(409, "This receivable is already locked.");
    return base;
  });
  const changed = vi.fn();
  render(<FinancingPanel row={row} onChanged={changed} />);
  fireEvent.click(
    await screen.findByRole("button", { name: "Review & accept" }),
  );
  fireEvent.click(screen.getByRole("button", { name: "Confirm acceptance" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("already locked");
  expect(changed).not.toHaveBeenCalled();
});
test("expired offers cannot be accepted and unavailable terms do not appear empty", async () => {
  call.mockResolvedValue({
    ...base,
    offers: [{ ...offer, status: "EXPIRED" }],
  });
  const { unmount } = render(<FinancingPanel row={row} onChanged={() => {}} />);
  expect(await screen.findByText("EXPIRED")).toBeVisible();
  expect(
    screen.queryByRole("button", { name: "Review & accept" }),
  ).not.toBeInTheDocument();
  unmount();
  call.mockRejectedValue(new Error("Terms unavailable"));
  render(<FinancingPanel row={row} onChanged={() => {}} />);
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Terms unavailable",
  );
  expect(screen.queryByText("No offers to show yet.")).not.toBeInTheDocument();
});
test("financier offer preserves exact decimal text and UTC expiry", async () => {
  user.role = "FINANCIER";
  call.mockResolvedValue({
    ...base,
    offers: [],
    can_offer: true,
    can_accept: false,
  });
  render(<FinancingPanel row={row} onChanged={() => {}} />);
  fireEvent.change(await screen.findByLabelText("Advance amount (EUR)"), {
    target: { value: "9750.01" },
  });
  fireEvent.change(screen.getByLabelText("Offer expires (your local time)"), {
    target: { value: "2099-01-01T12:00" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Submit offer" }));
  await waitFor(() =>
    expect(call).toHaveBeenCalledWith(
      "receivables/record-1/offers",
      expect.objectContaining({ method: "POST" }),
    ),
  );
  const submitted = call.mock.calls.find(
    ([, init]) => init?.method === "POST",
  )![1]!;
  expect(JSON.parse(submitted.body as string)).toMatchObject({
    advanceAmount: "9750.01",
    currency: "EUR",
    discountRateBps: 250,
    tenorDays: 60,
  });
  expect(JSON.parse(submitted.body as string).expiresAt).toMatch(/Z$/);
});
test("only authorized lock owner is offered an explicit sandbox payout control", async () => {
  user.role = "FINANCIER";
  call.mockResolvedValue({
    ...base,
    offers: [{ ...offer, status: "ACCEPTED" }],
    can_accept: false,
    can_disburse: true,
  });
  const changed = vi.fn();
  render(<FinancingPanel row={row} onChanged={changed} />);
  expect(
    await screen.findByText("NPCI Payment Adapter — Sandbox Simulation"),
  ).toBeVisible();
  fireEvent.click(
    screen.getByRole("button", { name: "Simulate disbursement" }),
  );
  await waitFor(() =>
    expect(call).toHaveBeenCalledWith(
      "receivables/record-1/disbursement/mock",
      { method: "POST" },
    ),
  );
  expect(changed).toHaveBeenCalledTimes(1);
});
test("financier dashboard uses sanitized value ranges and portfolio filters", async () => {
  call.mockResolvedValue({
    items: [
      {
        ...row,
        asset_id: "TC-1",
        exporter_org_id: "EXPORTER",
        face_value_bucket: "10000-25000",
        due_date: "2026-11-25",
      },
    ],
    total: 1,
    summary: { total: 1, available: 1, financed: 0, settled: 0 },
    recent_activity: [],
  });
  render(<FinancierDashboard />);
  expect(await screen.findByText("EUR 10000-25000")).toBeVisible();
  fireEvent.click(screen.getByRole("button", { name: "Assigned to us" }));
  await waitFor(() =>
    expect(call).toHaveBeenCalledWith(
      "receivables?view=assigned&limit=20&offset=0",
    ),
  );
});
