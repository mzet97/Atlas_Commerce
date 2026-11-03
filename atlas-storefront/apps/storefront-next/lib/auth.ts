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

/** Browser-visible origin (proxy maps :3100->:3000; Host header is truth). */
export function originOf(request: Request): string {
  const host =
    request.headers.get("x-forwarded-host") ?? request.headers.get("host");
  const proto =
    request.headers.get("x-forwarded-proto")
    ?? (host && host.startsWith("localhost") ? "http" : null);
  if (host) return `${proto ?? "http"}://${host}`;
  return new URL(request.url).origin;
}

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

type Jwk = { kty: string; n: string; e: string; kid?: string };
let jwksCache: Map<string, crypto.KeyObject> | null = null;
let jwksAt = 0;

async function realmKeys(): Promise<Map<string, crypto.KeyObject>> {
  if (!jwksCache || Date.now() - jwksAt > 3_600_000) {
    const response = await fetch(
      `${INTERNAL_URL}/realms/${REALM}/protocol/openid-connect/certs`,
      { cache: "no-store" },
    );
    const jwks = (await response.json()) as { keys: Jwk[] };
    jwksCache = new Map(
      jwks.keys.map((k) => [
        k.kid ?? "",
        crypto.createPublicKey({ key: k, format: "jwk" }),
      ]),
    );
    jwksAt = Date.now();
  }
  return jwksCache;
}

/**
 * Verified username: RS256 signature + expiry checked against the realm
 * JWKS (the cookie is only ever minted after a successful code exchange,
 * but claims are verified, never trusted). Cached 60s per token.
 */
export async function currentUser(
  token: string | undefined,
): Promise<string | null> {
  if (!token) return null;
  const cached = userCache.get(token);
  if (cached && Date.now() - cached.at < 60_000) return cached.username;
  try {
    const [headerB64, payloadB64, signatureB64] = token.split(".");
    if (!headerB64 || !payloadB64 || !signatureB64) return null;
    const header = JSON.parse(
      Buffer.from(headerB64, "base64url").toString(),
    ) as { alg?: string; kid?: string };
    const payload = JSON.parse(
      Buffer.from(payloadB64, "base64url").toString(),
    ) as { exp?: number; preferred_username?: string };
    if (header.alg !== "RS256") return null;
    if (typeof payload.exp === "number" && payload.exp * 1000 < Date.now())
      return null;
    const key = (await realmKeys()).get(header.kid ?? "");
    if (!key) return null;
    const valid = crypto.verify(
      "RSA-SHA256",
      Buffer.from(`${headerB64}.${payloadB64}`),
      key,
      Buffer.from(signatureB64, "base64url"),
    );
    if (!valid) return null;
    const username =
      typeof payload.preferred_username === "string"
        ? payload.preferred_username
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
