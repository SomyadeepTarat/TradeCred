// @vitest-environment node
import { afterEach, expect, test, vi } from "vitest";
import { NextRequest } from "next/server";
import { gateway } from "../lib/gateway";

afterEach(() => vi.unstubAllGlobals());
function request(
  path: string,
  method = "GET",
  headers: Record<string, string> = {},
) {
  return new NextRequest(`http://localhost:3000/api/backend/${path}`, {
    method,
    headers: {
      host: "localhost:3000",
      origin: "http://localhost:3000",
      ...headers,
    },
    ...(method === "POST" ? { body: "{}" } : {}),
  });
}
test("login stores JWT in HttpOnly cookie, never returns it to JavaScript", async () => {
  const fetcher = vi
    .fn()
    .mockResolvedValue(
      Response.json({ access_token: "secret-token", expires_in: 1800 }),
    );
  vi.stubGlobal("fetch", fetcher);
  const response = await gateway(request("auth/login", "POST"), [
    "auth",
    "login",
  ]);
  expect(response.status).toBe(200);
  expect(await response.json()).toEqual({ signedIn: true });
  const cookie = response.headers.get("set-cookie");
  expect(cookie).toContain("HttpOnly");
  expect(cookie).toContain("SameSite=strict");
  expect(response.headers.get("cache-control")).toBe("no-store");
});
test("proxy ignores caller Authorization and forwards its session cookie", async () => {
  const fetcher = vi.fn().mockResolvedValue(Response.json({ items: [] }));
  vi.stubGlobal("fetch", fetcher);
  await gateway(
    request("receivables", "GET", {
      cookie: "tradecred_session=real-token",
      Authorization: "Bearer forged",
    }),
    ["receivables"],
  );
  expect(fetcher.mock.calls[0][1].headers.get("Authorization")).toBe(
    "Bearer real-token",
  );
});
test("missing session and cross-origin writes never contact backend", async () => {
  const fetcher = vi.fn();
  vi.stubGlobal("fetch", fetcher);
  expect((await gateway(request("receivables"), ["receivables"])).status).toBe(
    401,
  );
  expect(
    (
      await gateway(
        request("receivables", "POST", { origin: "http://attacker.test" }),
        ["receivables"],
      )
    ).status,
  ).toBe(403);
  expect(fetcher).not.toHaveBeenCalled();
});
test("gateway refuses unimplemented endpoints and path traversal", async () => {
  expect(
    (await gateway(request("admin/delete"), ["admin", "delete"])).status,
  ).toBe(404);
  expect((await gateway(request("auth/me"), ["..", "auth", "me"])).status).toBe(
    404,
  );
});
test("upstream auth failure clears cookie and preserves status", async () => {
  vi.stubGlobal(
    "fetch",
    vi
      .fn()
      .mockResolvedValue(
        Response.json({ error: { message: "expired" } }, { status: 401 }),
      ),
  );
  const response = await gateway(
    request("auth/me", "GET", { cookie: "tradecred_session=expired" }),
    ["auth", "me"],
  );
  expect(response.status).toBe(401);
  expect(response.headers.get("set-cookie")).toContain("tradecred_session=;");
});
test("unavailable API returns an error and logout clears the session", async () => {
  vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("private host")));
  const response = await gateway(request("auth/login", "POST"), [
    "auth",
    "login",
  ]);
  expect(response.status).toBe(503);
  expect(await response.text()).not.toContain("private host");
  const logout = await gateway(request("auth/logout", "POST"), [
    "auth",
    "logout",
  ]);
  expect(logout.headers.get("set-cookie")).toContain("tradecred_session=;");
});
