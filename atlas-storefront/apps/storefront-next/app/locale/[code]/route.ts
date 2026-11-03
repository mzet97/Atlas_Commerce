import { originOf } from "@/lib/auth";
import { isLocale, LOCALE_COOKIE } from "@/lib/i18n";

export const dynamic = "force-dynamic";

/** Locale switcher: /locale/en-US -> cookie + back to the Referer page. */
export async function GET(
  request: Request,
  { params }: { params: Promise<{ code: string }> },
): Promise<Response> {
  const { code } = await params;
  const origin = originOf(request);
  if (!isLocale(code)) {
    return new Response(null, { status: 307, headers: { location: origin } });
  }
  const back = request.headers.get("referer") ?? origin;
  const safe = back.startsWith(origin) ? back : origin;
  return new Response(null, {
    status: 307,
    headers: {
      location: safe,
      "set-cookie": `${LOCALE_COOKIE}=${code}; Path=/; SameSite=Lax; Max-Age=31536000`,
    },
  });
}
