import {
  clearCookie,
  exchangeCode,
  originOf,
  sessionCookie,
  VERIFIER_COOKIE,
  STATE_COOKIE,
} from "@/lib/auth";

export const dynamic = "force-dynamic";

/** Auth Code + PKCE finish line: state must match the flow's cookie. */
export async function GET(request: Request): Promise<Response> {
  const origin = originOf(request);
  const params = new URL(request.url).searchParams;
  const code = params.get("code");
  const state = params.get("state");
  const verifier = readCookie(request, VERIFIER_COOKIE);
  const expectedState = readCookie(request, STATE_COOKIE);

  const fail = () =>
    new Response(null, {
      status: 307,
      headers: { location: `${origin}/?auth_error=1` },
    });

  if (!code || !verifier || !state || state !== expectedState) return fail();

  const tokens = await exchangeCode(code, verifier, origin);
  if (!tokens) return fail();

  const headers = new Headers({ location: origin });
  headers.append("set-cookie", sessionCookie(tokens.access_token, tokens.expires_in));
  headers.append("set-cookie", clearCookie(VERIFIER_COOKIE));
  headers.append("set-cookie", clearCookie(STATE_COOKIE));
  return new Response(null, { status: 307, headers });
}

function readCookie(request: Request, name: string): string | null {
  const header = request.headers.get("cookie") ?? "";
  for (const part of header.split(";")) {
    const [key, ...rest] = part.trim().split("=");
    if (key === name) return rest.join("=");
  }
  return null;
}
