import { authorizeUrl } from "@/lib/auth";

export const dynamic = "force-dynamic";

export function GET(request: Request): Response {
  const origin = new URL(request.url).origin;
  const { url, cookies } = authorizeUrl(origin);
  const headers = new Headers({ location: url });
  for (const cookie of cookies) headers.append("set-cookie", cookie);
  return new Response(null, { status: 307, headers });
}
