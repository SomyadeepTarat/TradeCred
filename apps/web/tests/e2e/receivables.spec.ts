import { expect, test, Page } from "@playwright/test";

async function login(page: Page, role: string) {
  await page.goto("/login");
  await page.getByLabel("Email address").fill(`${role}@tradecred.demo`);
  await page.getByLabel("Password").fill(process.env.E2E_PASSWORD!);
  await page.getByRole("button", { name: "Sign in →" }).click();
  await expect(page).toHaveURL("/receivables");
}
async function fill(page: Page) {
  await page.getByLabel("Buyer ID").fill("BUYER-DE-001");
  await page.getByLabel("Invoice number").fill("E2E-2026-1042");
  await page.getByLabel("Invoice date").fill("2026-09-21");
  await page.getByLabel("Due date").fill("2026-11-25");
  await page.getByLabel("Face value", { exact: true }).fill("10800.00");
  await page
    .getByLabel("Original invoice PDF")
    .setInputFiles(process.env.E2E_PDF_PATH!);
}
test("exporter creates, admin verifies, exporter registers and checks history", async ({
  page,
}, testInfo) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await login(page, "exporter");
  await expect(
    page.getByRole("heading", { name: "Your receivables" }),
  ).toBeVisible();
  await page
    .getByRole("main")
    .getByRole("link", { name: "＋ Create receivable" })
    .click();
  await fill(page);
  await page.getByRole("button", { name: "Create draft →" }).click();
  await expect(
    page.getByRole("heading", { name: "E2E-2026-1042" }),
  ).toBeVisible();
  const detailURL = page.url();
  await expect(
    page.getByText("No registered match", { exact: true }),
  ).toBeVisible();
  await expect(page.locator(".hash-grid code").first()).toHaveText(
    /^[a-f0-9]{64}$/,
  );
  await page.getByRole("button", { name: "Check PDF integrity" }).click();
  await expect(page.getByText(/Document integrity verified/)).toBeVisible();
  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("link", { name: "Download PDF ↓" }).click();
  expect((await downloadPromise).suggestedFilename()).toMatch(
    /^invoice-.*\.pdf$/,
  );
  await page.getByRole("button", { name: "Submit for verification" }).click();
  await expect(
    page.getByText(/Awaiting administrator verification/),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Verify invoice integrity" }),
  ).toHaveCount(0);
  await page.getByRole("button", { name: "Sign out" }).click();
  await login(page, "admin");
  await page.goto(detailURL);
  await expect(page.getByText("Private value", { exact: true })).toBeVisible();
  await expect(page.getByRole("link", { name: "Download PDF ↓" })).toHaveCount(
    0,
  );
  await page.getByRole("button", { name: "Verify invoice integrity" }).click();
  await expect(
    page.getByText("Verification is recorded.", { exact: false }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Sign out" }).click();
  await login(page, "exporter");
  await page.goto(detailURL);
  await page.getByRole("button", { name: "Register receivable" }).click();
  await expect(
    page.getByText("This asset is registered", { exact: true }),
  ).toBeVisible();
  await expect(page.locator(".transaction-list code")).toHaveText(/^MOCK-/);
  await page.getByRole("button", { name: "Open for financing" }).click();
  await expect(
    page.getByText(/This receivable is open for financing/),
  ).toBeVisible();
  await expect(page.locator(".timeline li")).toHaveCount(5);
  await expect(page.locator(".transaction-list li")).toHaveCount(2);
  await page.screenshot({
    path: testInfo.outputPath("receivable-desktop.png"),
    fullPage: true,
  });
  await page.reload();
  await expect(
    page.getByText(/This receivable is open for financing/),
  ).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({
    path: testInfo.outputPath("receivable-mobile.png"),
    fullPage: true,
  });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto("/receivables");
  await expect(
    page.getByRole("link", { name: "E2E-2026-1042", exact: true }),
  ).toBeVisible();
  await page.screenshot({
    path: testInfo.outputPath("dashboard-desktop.png"),
    fullPage: true,
  });
  await page.goto("/receivables/new");
  await fill(page);
  await page.getByRole("button", { name: "Create draft →" }).click();
  await expect(page.getByRole("main").getByRole("alert")).toContainText(
    "already recorded locally",
  );
  await expect(page.getByLabel("Invoice number")).toHaveValue("E2E-2026-1042");
  expect(errors).toEqual([]);
});
test("expired session returns to login and settlement operator has no exporter controls", async ({
  page,
  context,
}) => {
  await login(page, "exporter");
  await context.clearCookies();
  await page.reload();
  await expect(page).toHaveURL("/login");
  await login(page, "settlement");
  await expect(
    page.getByRole("heading", { name: "Settlement simulator" }),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: /Create receivable/ }),
  ).toHaveCount(0);
});
