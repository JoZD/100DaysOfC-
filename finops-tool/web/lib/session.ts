import { cookies } from "next/headers";
import { redirect } from "next/navigation";

// The API issues a signed token at /auth/login (services/api/auth.py). It is
// kept in an httpOnly cookie, sent to the API as a bearer token from server
// code only, and never exposed to browser JavaScript. The API verifies it on
// every request; this module only reads it.
export const SESSION_COOKIE = "finops_session";

export interface Session {
  token: string;
  email: string;
}

function decodePayload(token: string): { email?: string; exp?: number } | null {
  try {
    const payload = token.split(".")[1];
    return JSON.parse(Buffer.from(payload, "base64url").toString("utf8"));
  } catch {
    return null;
  }
}

export async function getSession(): Promise<Session | null> {
  const token = (await cookies()).get(SESSION_COOKIE)?.value;
  if (!token) return null;
  const payload = decodePayload(token);
  if (!payload?.exp || payload.exp * 1000 <= Date.now()) return null;
  return { token, email: payload.email ?? "" };
}

/** For pages and server actions: the session, or a redirect to the sign-in page. */
export async function requireSession(): Promise<Session> {
  const session = await getSession();
  if (!session) redirect("/login");
  return session;
}

// Secure cookies need HTTPS; internal plain-HTTP deployments leave this unset.
export function cookieSecure(): boolean {
  return ["1", "true", "yes"].includes((process.env.COOKIE_SECURE ?? "").toLowerCase());
}
