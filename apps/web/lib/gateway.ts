import { NextRequest, NextResponse } from "next/server";

const COOKIE = "tradecred_session";
const MAX_BODY = 50 * 1024 * 1024 + 65536;
const UUID = "[0-9a-fA-F-]{36}";
const allowedGet = new RegExp(
  `^(auth/me|audit/events|audit/security-events|simulator/assets|receivables|receivables/${UUID}(/history|/document|/document/integrity|/offers)?|registry/fingerprint/[a-f0-9]{64})$`,
);
const allowedPost = new RegExp(
  `^(auth/login|auth/logout|registry/check|simulator/events|simulator/events/${UUID}/replay|receivables|receivables/${UUID}/(submit|verify|register|open-financing|realize|ebrc-eligible|close|offers|disbursement/mock)|offers/${UUID}/(accept|reject))$`,
);

function error(status: number, message: string) {
  return NextResponse.json(
    { error: { message } },
    { status, headers: { "Cache-Control": "no-store" } },
  );
}

export async function gateway(request: NextRequest, path: string[]) {
  const endpoint = path.join("/");
  const post = request.method === "POST";
  if (!(post ? allowedPost : allowedGet).test(endpoint))
    return error(404, "Endpoint not found.");
  // Cookie-authenticated mutations must originate from this website.
  if (post) {
    const origin = request.headers.get("origin");
    try {
      if (
        !origin ||
        new URL(origin).host !== request.headers.get("host") ||
        !["http:", "https:"].includes(new URL(origin).protocol)
      )
        return error(403, "Request origin is not allowed.");
    } catch {
      return error(403, "Request origin is not allowed.");
    }
  }
  if (endpoint === "auth/logout") {
    const response = NextResponse.json(
      { signedOut: true },
      { headers: { "Cache-Control": "no-store" } },
    );
    response.cookies.delete(COOKIE);
    return response;
  }
  const token = request.cookies.get(COOKIE)?.value;
  if (endpoint !== "auth/login" && !token)
    return error(401, "Please sign in to continue.");
  const headers = new Headers();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const contentType = request.headers.get("content-type");
  if (contentType) headers.set("Content-Type", contentType);
  try {
    let body: Uint8Array | undefined;
    if (post && request.body) {
      const reader = request.body.getReader();
      const chunks: Uint8Array[] = [];
      let size = 0;
      while (true) {
        const chunk = await reader.read();
        if (chunk.done) break;
        size += chunk.value.length;
        if (size > MAX_BODY) {
          await reader.cancel();
          return error(413, "Upload is too large.");
        }
        chunks.push(chunk.value);
      }
      body = new Uint8Array(size);
      let offset = 0;
      for (const chunk of chunks) {
        body.set(chunk, offset);
        offset += chunk.length;
      }
    }
    const base = process.env.API_INTERNAL_URL || "http://127.0.0.1:8000";
    const upstream = await fetch(
      `${base}/api/v1/${endpoint}${request.nextUrl.search}`,
      {
        method: request.method,
        headers,
        body: body as BodyInit | undefined,
        cache: "no-store",
        redirect: "error",
        signal: AbortSignal.timeout(30000),
      },
    );
    if (endpoint === "auth/login" && upstream.ok) {
      const login = await upstream.json();
      const response = NextResponse.json(
        { signedIn: true },
        { headers: { "Cache-Control": "no-store" } },
      );
      response.cookies.set(COOKIE, login.access_token, {
        httpOnly: true,
        sameSite: "strict",
        secure: request.nextUrl.protocol === "https:",
        path: "/",
        maxAge: login.expires_in,
      });
      return response;
    }
    const response = new NextResponse(upstream.body, {
      status: upstream.status,
    });
    for (const name of [
      "content-type",
      "content-disposition",
      "x-request-id",
      "content-security-policy",
      "x-content-type-options",
    ]) {
      const value = upstream.headers.get(name);
      if (value) response.headers.set(name, value);
    }
    response.headers.set("Cache-Control", "no-store");
    if (upstream.status === 401) response.cookies.delete(COOKIE);
    return response;
  } catch {
    return error(
      503,
      "The API is unavailable or the request timed out. Refresh the receivable before retrying; the previous request may have completed.",
    );
  }
}
