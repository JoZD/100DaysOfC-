"use server";

import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { ApiError, login } from "@/lib/api";
import { SESSION_COOKIE, cookieSecure } from "@/lib/session";

export interface LoginState {
  error?: string;
  // React resets the form after an action; the email is restored from here.
  email?: string;
}

export async function loginAction(_prev: LoginState, form: FormData): Promise<LoginState> {
  const email = String(form.get("email") ?? "").trim();
  const password = String(form.get("password") ?? "");
  if (!email || !password) return { error: "Enter your email and password.", email };

  try {
    const { access_token, expires_at } = await login(email, password);
    (await cookies()).set(SESSION_COOKIE, access_token, {
      httpOnly: true,
      sameSite: "lax",
      secure: cookieSecure(),
      path: "/",
      expires: new Date(expires_at),
    });
  } catch (err) {
    if (err instanceof ApiError && (err.status === 401 || err.status === 422)) {
      return { error: "Invalid email or password.", email };
    }
    throw err;
  }
  redirect("/dashboard");
}
