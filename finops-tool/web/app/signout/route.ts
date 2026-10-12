import { SESSION_COOKIE } from "@/lib/session";

// Clears the session cookie and returns to the sign-in page. The Location is
// relative on purpose: inside Docker the server sees http://0.0.0.0:3000, so
// an absolute URL built from the request would send the browser elsewhere.
export function GET() {
  return new Response(null, {
    status: 303,
    headers: {
      Location: "/login",
      "Set-Cookie": `${SESSION_COOKIE}=; Path=/; Max-Age=0; HttpOnly; SameSite=Lax`,
    },
  });
}
