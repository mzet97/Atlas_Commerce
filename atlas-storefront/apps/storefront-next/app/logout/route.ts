import { clearCookie, originOf, SESSION_COOKIE } from "@/lib/auth";

export const dynamic = "force-dynamic";

/** Local session end (SSO session at the realm may outlive this). */
export function GET(request: Request): Response {
  const origin = originOf(request);
  return new Response(null, {
    status: 307,
    headers: {
      location: origin,
      "set-cookie": clearCookie(SESSION_COOKIE),
    },
  });
}
