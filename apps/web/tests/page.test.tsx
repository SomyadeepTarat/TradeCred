import {
  fireEvent,
  render,
  screen,
  waitFor,
  cleanup,
} from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { Login } from "../components/login";
import { Dashboard } from "../components/dashboard";
import { CreateReceivable } from "../components/create-receivable";
import { ReceivableDetail } from "../components/receivable-detail";
import { api, ApiError, money, Receivable } from "../lib/api";

const { push, replace, user } = vi.hoisted(() => ({
  push: vi.fn(),
  replace: vi.fn(),
  user: {
    id: "u",
    role: "EXPORTER",
    organization_id: "ORG_EXPORTER_ALPHA",
    display_name: "Demo Exporter",
  },
}));
const router = { push, replace };
vi.mock("next/navigation", () => ({ useRouter: () => router }));
vi.mock("../lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../lib/api")>()),
  api: vi.fn(),
}));
vi.mock("../components/workspace", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../components/workspace")>()),
  useUser: () => user,
}));
const mockApi = vi.mocked(api);
const row = {
  id: "id-1",
  invoice_number: "EXP-1",
  buyer_id: "BUYER-1",
  invoice_date: "2026-09-21",
  due_date: "2026-11-25",
  face_value: "10800.00",
  currency: "EUR",
  status: "DRAFT",
  asset_id: null,
  invoice_fingerprint: "a".repeat(64),
  document_hash: "b".repeat(64),
  exporter_org_id: "ORG_EXPORTER_ALPHA",
  available_actions: ["submit"],
  ledger_backend: "mock",
  document_available: true,
};
beforeEach(() => {
  vi.clearAllMocks();
  user.role = "EXPORTER";
});
afterEach(cleanup);

test("login sends entered credentials and redirects only after success", async () => {
  mockApi.mockResolvedValue({ signedIn: true });
  render(<Login />);
  fireEvent.change(screen.getByLabelText("Password"), {
    target: { value: "my-demo-password" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Sign in →" }));
  await waitFor(() => expect(replace).toHaveBeenCalledWith("/receivables"));
  expect(mockApi).toHaveBeenCalledWith(
    "auth/login",
    expect.objectContaining({
      body: JSON.stringify({
        email: "exporter@tradecred.demo",
        password: "my-demo-password",
      }),
    }),
  );
});
test("invalid credentials remain on login with an error", async () => {
  mockApi.mockRejectedValue(new ApiError(401, "Invalid credentials."));
  render(<Login />);
  fireEvent.change(screen.getByLabelText("Password"), {
    target: { value: "wrong" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Sign in →" }));
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Invalid credentials",
  );
  expect(replace).not.toHaveBeenCalled();
});
test("dashboard renders actual counts, records and status filter", async () => {
  mockApi.mockResolvedValue({
    items: [row],
    total: 1,
    summary: { total: 1, available: 0, financed: 0, settled: 0 },
    recent_activity: [],
  });
  render(<Dashboard />);
  expect(await screen.findByRole("link", { name: "EXP-1" })).toHaveAttribute(
    "href",
    "/receivables/id-1",
  );
  expect(screen.getByText("EUR 10,800.00")).toBeVisible();
  fireEvent.change(screen.getByLabelText("Filter by status"), {
    target: { value: "SUBMITTED" },
  });
  await waitFor(() =>
    expect(mockApi).toHaveBeenCalledWith(
      "receivables?limit=20&offset=0&status=SUBMITTED",
    ),
  );
});
test("unavailable dashboard does not pretend the register is empty", async () => {
  mockApi.mockRejectedValue(new Error("API unavailable"));
  render(<Dashboard />);
  expect(await screen.findByRole("alert")).toHaveTextContent("API unavailable");
  expect(
    screen.queryByText("Your register starts here"),
  ).not.toBeInTheDocument();
});
function fillInvoice() {
  for (const [label, value] of [
    ["Buyer ID", "BUYER-1"],
    ["Invoice number", "EXP-1"],
    ["Invoice date", "2026-09-21"],
    ["Due date", "2026-11-25"],
    ["Face value", "10800.00"],
  ])
    fireEvent.change(screen.getByLabelText(label), { target: { value } });
  fireEvent.change(screen.getByLabelText("Original invoice PDF"), {
    target: {
      files: [new File(["pdf"], "invoice.pdf", { type: "application/pdf" })],
    },
  });
}
test("create form sends decimal text and PDF, then opens the saved draft", async () => {
  mockApi.mockResolvedValue({ id: "new-id" });
  render(<CreateReceivable />);
  fillInvoice();
  // jsdom FormData does not retain input file bytes; use its File constructor payload via a spy.
  const original = globalThis.FormData;
  vi.stubGlobal(
    "FormData",
    class extends original {
      constructor(form?: HTMLFormElement) {
        super(form);
        if (form)
          this.set(
            "document",
            new File(["pdf"], "invoice.pdf", { type: "application/pdf" }),
          );
      }
    },
  );
  try {
    fireEvent.submit(
      screen.getByRole("button", { name: "Create draft →" }).closest("form")!,
    );
    await waitFor(() =>
      expect(push).toHaveBeenCalledWith("/receivables/new-id"),
    );
    const form = mockApi.mock.calls[0][1]?.body as FormData;
    expect(JSON.parse(form.get("metadata") as string).amount).toBe("10800.00");
    expect(form.get("document")).toBeInstanceOf(File);
  } finally {
    vi.unstubAllGlobals();
  }
});
test("detail shows full hashes, unknown registry on failure, and no invented history", async () => {
  mockApi.mockImplementation(async (path) => {
    if (path.endsWith("/history")) return { events: [], ledger: [] };
    if (path.startsWith("registry/")) throw new Error("offline");
    return row;
  });
  render(<ReceivableDetail id="id-1" />);
  expect(await screen.findByText("a".repeat(64))).toBeVisible();
  expect(screen.getByText("b".repeat(64))).toBeVisible();
  expect(screen.getByText(/Duplicate status is unknown/)).toBeVisible();
  expect(
    screen.getByText("No ledger transactions recorded yet."),
  ).toBeVisible();
  expect(
    screen.getByRole("button", { name: "Submit for verification" }),
  ).toBeVisible();
  expect(
    screen.queryByRole("button", { name: "Verify invoice integrity" }),
  ).not.toBeInTheDocument();
});
test("failed lifecycle action displays error without advancing status", async () => {
  mockApi.mockImplementation(async (path, init) => {
    if (init?.method === "POST") throw new ApiError(503, "Ledger unavailable");
    if (path.endsWith("/history")) return { events: [], ledger: [] };
    if (path.startsWith("registry/"))
      return { exists: false, eligible: true, backend: "mock" };
    return { ...row, status: "VERIFIED", available_actions: ["register"] };
  });
  render(<ReceivableDetail id="id-1" />);
  fireEvent.click(
    await screen.findByRole("button", { name: "Register receivable" }),
  );
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Ledger unavailable",
  );
  expect(
    screen.queryByText("Registration is recorded."),
  ).not.toBeInTheDocument();
});
test("amount display preserves integer precision and fractional digits", () => {
  expect(
    money({
      face_value: "92233720368547758.07",
      currency: "EUR",
    } as Receivable),
  ).toBe("EUR 92,233,720,368,547,758.07");
  expect(money({ face_value: "123.1234", currency: "CLF" } as Receivable)).toBe(
    "CLF 123.1234",
  );
});
