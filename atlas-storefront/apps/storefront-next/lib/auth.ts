import crypto from "node:crypto";

/**
 * OIDC Auth Code + PKCE (RFC 7636) against the Keycloak `atlas` realm,
 * client `atlas-storefront` (public, standard flow). No external deps.
 *
 * PUBLIC_URL is what the BROWSER must reach (authorize redirect);
 * INTERNAL_URL is what the SERVER fetches (token/userinfo) — they differ
 * inside compose (keycloak:8080) vs on the host (localhost:8180).
 */

const PUBLIC_URL = process.env.KC_PUBLIC_URL ?? "http://localhost:8180";
const INTERNAL_URL = process.env.KC_INTERNAL_URL ?? PUBLIC_URL;
const REALM = "atlas";
const CLIENT_ID = "atlas-storefront";

export const SESSION_COOKIE = "atlas_session";
export const VERIFIER_COOKIE = "atlas_pkce_verifier";
export const STATE_COOKIE = "atlas_pkce_state";

export function authorizeUrl(origin: string): {
  url: string;
  cookies: string[];
} {
  const verifier = crypto.randomBytes(48).toString("base64url");
  const challenge = crypto
    .createHash("sha256")
    .update(verifier)
    .digest("base64url");
  const state = crypto.randomBytes(16).toString("base64url");
  const params = new URLSearchParams({
    response_type: "code",
    client_id: CLIENT_ID,
    scope: "openid profile",
    state,
    nonce: crypto.randomBytes(16).toString("base64url"),
    code_challenge: challenge,
    code_challenge_method: "S256",
    redirect_uri: `${origin}/callback`,
  });
  // Verifier/state ride in short-lived httpOnly cookies: the server that
  // started the flow is the only one able to finish it.
  const cookies = [
    `${VERIFIER_COOKIE}=${verifier}; Path=/; HttpOnly; SameSite=Lax; Max-Age=600`,
    `${STATE_COOKIE}=${state}; Path=/; HttpOnly; SameSite=Lax; Max-Age=600`,
  ];
  return {
    url: `${PUBLIC_URL}/realms/${REALM}/protocol/openid-connect/auth?${params}`,
    cookies,
  };
}

type Tokens = { access_token: string; expires_in: number };

export async function exchangeCode(
  code: string,
  verifier: string,
  origin: string,
): Promise<Tokens | null> {
  const response = await fetch(
    `${INTERNAL_URL}/realms/${REALM}/protocol/openid-connect/token`,
    {
      method: "POST",
      headers: { "content-type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({
        grant_type: "authorization_code",
        client_id: CLIENT_ID,
        code,
        code_verifier: verifier,
        redirect_uri: `${origin}/callback`,
      }),
      cache: "no-store",
    },
  );
  if (!response.ok) return null;
  const data = (await response.json()) as Partial<Tokens>;
  if (typeof data.access_token !== "string" || typeof data.expires_in !== "number")
    return null;
  return { access_token: data.access_token, expires_in: data.expires_in };
}

export function sessionCookie(token: string, maxAgeSeconds: number): string {
  return `${SESSION_COOKIE}=${token}; Path=/; HttpOnly; SameSite=Lax; Max-Age=${maxAgeSeconds}`;
}

export function clearCookie(name: string): string {
  return `${name}=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0`;
}

const userCache = new Map<string, { username: string; at: number }>();

/** Verified username via userinfo (server-side, cached 60s per token). */
export async function currentUser(
  token: string | undefined,
): Promise<string | null> {
  if (!token) return null;
  const cached = userCache.get(token);
  if (cached && Date.now() - cached.at < 60_000) return cached.username;
  try {
    const response = await fetch(
      `${INTERNAL_URL}/realms/${REALM}/protocol/openid-connect/userinfo`,
      { headers: { authorization: `Bearer ${token}` }, cache: "no-store" },
    );
    if (!response.ok) return null;
    const data = (await response.json()) as { preferred_username?: string };
    const username = typeof data.preferred_username === "string"
      ? data.preferred_username
      : null;
    if (username) {
      userCache.set(token, { username, at: Date.now() });
      if (userCache.size > 500) userCache.clear();
    }
    return username;
  } catch {
    return null;
  }
}
