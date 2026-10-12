import { redirect } from "next/navigation";

import { LoginForm } from "@/app/login/LoginForm";
import { getSession } from "@/lib/session";

export const dynamic = "force-dynamic";

export default async function LoginPage() {
  if (await getSession()) redirect("/dashboard");

  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-6 px-6 text-center">
      <div className="flex flex-col gap-2">
        <h1 className="text-3xl font-semibold tracking-tight">FinOps Tool</h1>
        <p className="text-muted-foreground">Sign in to see your AWS savings opportunities.</p>
      </div>
      <div className="w-full max-w-sm rounded-xl border bg-card p-6 shadow-xs">
        <LoginForm />
      </div>
      <p className="max-w-sm text-xs text-muted-foreground">
        Accounts are created by the operator with <code>scripts.admin create-user</code>.
      </p>
    </main>
  );
}
