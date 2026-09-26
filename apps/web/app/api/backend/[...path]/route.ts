import { NextRequest } from "next/server";
import { gateway } from "../../../../lib/gateway";

export const runtime = "nodejs";
export async function GET(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> },
) {
  return gateway(request, (await context.params).path);
}
export const POST = GET;
