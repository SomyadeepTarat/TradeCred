import { expect, test } from "@playwright/test";

test("browser receives correlated, private-safe proxy and API errors", async ({
  page,
}) => {
  await page.goto("/login");
  const results = await page.evaluate(async () => {
    const responses = [
      await fetch("/api/backend/receivables"),
      await fetch("/api/backend/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ password: "PRIVATE-INPUT" }),
      }),
    ];
    return Promise.all(
      responses.map(async (response) => ({
        status: response.status,
        requestId: response.headers.get("X-Request-ID"),
        cache: response.headers.get("Cache-Control"),
        body: await response.json(),
      })),
    );
  });
  expect(results.map((result) => result.status)).toEqual([401, 422]);
  expect(results.map((result) => result.body.error.code)).toEqual([
    "AUTHENTICATION_REQUIRED",
    "INVALID_REQUEST",
  ]);
  for (const result of results) {
    expect(result.requestId).toMatch(/^[a-f0-9-]{36}$/);
    expect(result.body.error.requestId).toBe(result.requestId);
    expect(result.body.error.details).toEqual({});
    expect(result.cache).toBe("no-store");
    expect(JSON.stringify(result.body)).not.toContain("PRIVATE-INPUT");
  }
  expect(results[0].requestId).not.toBe(results[1].requestId);
});
