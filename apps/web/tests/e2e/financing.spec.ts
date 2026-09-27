import { readFileSync } from "node:fs";
import { expect, test, Page } from "@playwright/test";

async function signIn(page: Page, role: string) {
  await page.goto("/login");
  await page.getByLabel("Email address").fill(`${role}@tradecred.demo`);
  await page.getByLabel("Password").fill(process.env.E2E_PASSWORD!);
  await page.getByRole("button", { name: "Sign in →" }).click();
  await expect(page).toHaveURL("/receivables");
}

test("two institutions offer, one is accepted and only that institution can simulate financing", async ({
  page,
  request,
}, testInfo) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  async function token(role: string) {
    const response = await request.post(
      "http://127.0.0.1:8001/api/v1/auth/login",
      {
        data: {
          email: `${role}@tradecred.demo`,
          password: process.env.E2E_PASSWORD,
        },
      },
    );
    expect(response.ok()).toBeTruthy();
    return { Authorization: `Bearer ${(await response.json()).access_token}` };
  }
  const exporter = await token("exporter");
  const admin = await token("admin");
  const created = await request.post(
    "http://127.0.0.1:8001/api/v1/receivables",
    {
      headers: exporter,
      multipart: {
        metadata: JSON.stringify({
          buyerId: "BUYER-DE-001",
          invoiceNumber: "E2E-FINANCE-001",
          invoiceDate: "2026-09-21",
          dueDate: "2026-11-25",
          currency: "EUR",
          amount: "10800.00",
        }),
        document: {
          name: "invoice.pdf",
          mimeType: "application/pdf",
          buffer: readFileSync(process.env.E2E_PDF_PATH!),
        },
      },
    },
  );
  expect(created.status()).toBe(201);
  const id = (await created.json()).id;
  for (const step of ["submit", "verify", "register", "open-financing"]) {
    const response = await request.post(
      `http://127.0.0.1:8001/api/v1/receivables/${id}/${step}`,
      { headers: step === "verify" ? admin : exporter },
    );
    expect(response.ok()).toBeTruthy();
  }
  const detail = `/receivables/${id}`;
  await signIn(page, "bank");
  await expect(
    page.getByRole("heading", { name: "Financier workspace" }),
  ).toBeVisible();
  await page.goto(detail);
  await expect(
    page.getByText("EUR 10000-25000", { exact: true }),
  ).toBeVisible();
  await expect(page.getByText("EUR 10,800.00", { exact: true })).toHaveCount(0);
  await page.getByLabel("Advance amount (EUR)").fill("9750.00");
  await page.getByRole("button", { name: "Submit offer" }).click();
  await expect(page.getByText(/Offer submitted/)).toBeVisible();
  await page.getByRole("button", { name: "Sign out" }).click();
  await signIn(page, "nbfc");
  await page.goto(detail);
  await expect(page.locator(".offer-card")).toHaveCount(0);
  await page.getByLabel("Advance amount (EUR)").fill("9500.00");
  await page.getByRole("button", { name: "Submit offer" }).click();
  await expect(page.getByText(/Offer submitted/)).toBeVisible();
  await page.getByRole("button", { name: "Sign out" }).click();
  await signIn(page, "exporter");
  await page.goto(detail);
  await expect(page.locator(".offer-card")).toHaveCount(2);
  await page
    .locator(".offer-card")
    .filter({ hasText: "ORG_BANK_CITI_DEMO" })
    .getByRole("button", { name: "Review & accept" })
    .click();
  await expect(
    page.getByRole("region", { name: "Confirm financing terms" }),
  ).toContainText("EUR 9,750.00");
  await page.getByRole("button", { name: "Confirm acceptance" }).click();
  await expect(
    page.getByText(/An offer is accepted and this receivable is locked/),
  ).toBeVisible();
  await expect(
    page.locator(".offer-card").filter({ hasText: "ORG_BANK_NBFC_DEMO" }),
  ).toContainText("REJECTED");
  await expect(page.locator(".agreement code").first()).toHaveText(
    /^[a-f0-9]{64}$/,
  );
  await page.getByText("View canonical agreement (TC-AGR-1)").click();
  await expect(page.locator(".agreement pre")).toContainText(
    '"advanceAmountMinor":975000',
  );
  await page.screenshot({
    path: testInfo.outputPath("accepted-offers.png"),
    fullPage: true,
  });
  await page.getByRole("button", { name: "Sign out" }).click();
  await signIn(page, "bank");
  await page.getByRole("button", { name: "Assigned to us" }).click();
  await expect(
    page.getByRole("main").getByRole("link", { name: /TC-/ }),
  ).toHaveCount(1);
  await page.goto(detail);
  await expect(page.locator(".offer-card")).toHaveCount(1);
  await expect(
    page.getByText("NPCI Payment Adapter — Sandbox Simulation"),
  ).toBeVisible();
  await page.getByRole("button", { name: "Simulate disbursement" }).click();
  await expect(
    page.getByText("SIMULATED SUCCEEDED", { exact: true }),
  ).toBeVisible();
  await expect(page.locator(".simulation code")).toHaveText(/^MOCKPAY-/);
  await expect(
    page.getByRole("button", { name: "Simulate disbursement" }),
  ).toHaveCount(0);
  await page.reload();
  await expect(page.locator(".simulation code")).toHaveText(/^MOCKPAY-/);
  await page.screenshot({
    path: testInfo.outputPath("financed-institution.png"),
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: testInfo.outputPath("financed-mobile.png"),
    fullPage: true,
  });
  await page.getByRole("button", { name: "Sign out" }).click();
  await signIn(page, "nbfc");
  await page.goto(detail);
  await expect(page.locator(".offer-card")).toHaveCount(1);
  await expect(page.locator(".offer-card")).toContainText("REJECTED");
  await expect(
    page.getByRole("button", { name: "Simulate disbursement" }),
  ).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Submit offer" })).toHaveCount(
    0,
  );
  const blocked = await page.request.post(
    `/api/backend/receivables/${id}/disbursement/mock`,
    { headers: { Origin: "http://127.0.0.1:3001" } },
  );
  expect(blocked.status()).toBe(403);
  const second = await page.request.post(
    `/api/backend/receivables/${id}/offers`,
    {
      headers: { Origin: "http://127.0.0.1:3001" },
      data: {
        advanceAmount: "9000.00",
        currency: "EUR",
        discountRateBps: 250,
        tenorDays: 60,
        expiresAt: new Date(Date.now() + 86400000).toISOString(),
      },
    },
  );
  expect(second.status()).toBe(409);
  expect((await second.json()).error.code).toBe("RECEIVABLE_ALREADY_FINANCED");
  expect(errors).toEqual([]);
});
