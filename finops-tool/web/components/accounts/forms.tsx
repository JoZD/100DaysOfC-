"use client";

import { useActionState, useEffect, type ReactNode } from "react";
import { useFormStatus } from "react-dom";
import { useRouter } from "next/navigation";
import { CircleAlert, CircleCheck, Loader2, Play, ShieldCheck, Trash2 } from "lucide-react";

import {
  changeRoleAction,
  createAccountAction,
  createWorkspaceAction,
  deleteAccountAction,
  scanAccountAction,
  verifyAccountAction,
  type FormState,
  type VerifyState,
} from "@/app/dashboard/actions";
import { Button } from "@/components/ui/button";

const inputClass =
  "h-9 w-full rounded-lg border bg-background px-3 text-sm outline-none transition-shadow placeholder:text-muted-foreground/70 focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50";

export function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: ReactNode;
  children: ReactNode;
}) {
  return (
    <label className="flex flex-col gap-1.5 text-sm">
      <span className="font-medium">{label}</span>
      {children}
      {hint ? <span className="text-xs text-muted-foreground">{hint}</span> : null}
    </label>
  );
}

function SubmitButton({
  children,
  pendingLabel,
  variant,
  icon,
}: {
  children: ReactNode;
  pendingLabel: string;
  variant?: "default" | "outline" | "destructive";
  icon?: ReactNode;
}) {
  const { pending } = useFormStatus();
  return (
    <Button type="submit" size="lg" variant={variant} disabled={pending}>
      {pending ? <Loader2 aria-hidden className="animate-spin" /> : icon}
      {pending ? pendingLabel : children}
    </Button>
  );
}

function FormError({ error }: { error?: string }) {
  if (!error) return null;
  return (
    <p role="alert" className="flex items-start gap-2 rounded-lg border border-destructive/30 bg-destructive/5 px-3 py-2 text-sm text-destructive">
      <CircleAlert aria-hidden className="mt-0.5 size-4 shrink-0" />
      {error}
    </p>
  );
}

export function WorkspaceForm() {
  const [state, action] = useActionState<FormState, FormData>(createWorkspaceAction, {});
  return (
    <form action={action} className="flex w-full max-w-md flex-col gap-4 text-left">
      <Field label="Workspace name" hint="Letters, numbers, spaces, dots, dashes. Shown only inside this app.">
        <input name="name" required maxLength={63} pattern="[A-Za-z0-9][A-Za-z0-9 ._\-]*" className={inputClass} placeholder="platform-team" />
      </Field>
      <FormError error={state.error} />
      <div>
        <SubmitButton pendingLabel="Creating…">Create workspace</SubmitButton>
      </div>
    </form>
  );
}

export function NewAccountForm({ defaultRoleName }: { defaultRoleName: string }) {
  const [state, action] = useActionState<FormState, FormData>(createAccountAction, {});
  return (
    <form action={action} className="flex max-w-lg flex-col gap-4">
      <Field label="Display name" hint="How this account appears in the dashboard, e.g. prod-payments.">
        <input name="name" required maxLength={63} pattern="[A-Za-z0-9][A-Za-z0-9 ._\-]*" className={inputClass} placeholder="prod-payments" />
      </Field>
      <Field label="AWS account ID" hint="The 12-digit ID of the account to analyze.">
        <input
          name="account_number"
          required
          inputMode="numeric"
          pattern="[0-9 \-]{12,14}"
          className={`${inputClass} font-mono`}
          placeholder="123456789012"
        />
      </Field>
      <Field label="IAM role name" hint="Keep the default. Any other name must start with FinOps-ReadOnly.">
        <input name="role_name" maxLength={64} defaultValue={defaultRoleName} className={`${inputClass} font-mono`} />
      </Field>
      <FormError error={state.error} />
      <div>
        <SubmitButton pendingLabel="Registering…">Continue to role setup</SubmitButton>
      </div>
    </form>
  );
}

const STAGE_LABEL: Record<string, string> = {
  source: "Reading this server's AWS identity",
  assume_role: "Assuming the role",
  identity: "Checking the assumed identity",
  permissions: "Checking read permissions",
  done: "Done",
};

export function VerifyPanel({ id }: { id: string }) {
  const [state, action] = useActionState<VerifyState, FormData>(verifyAccountAction.bind(null, id), {});
  const result = state.result;
  return (
    <div className="flex flex-col gap-3">
      <form action={action}>
        <SubmitButton pendingLabel="Checking…" icon={<ShieldCheck aria-hidden />}>
          Verify connection
        </SubmitButton>
      </form>
      <FormError error={state.error} />
      {result?.ok ? (
        <div role="status" className="flex items-start gap-2 rounded-lg border border-status-good/40 bg-status-good/5 px-3 py-2 text-sm">
          <CircleCheck aria-hidden className="mt-0.5 size-4 shrink-0 text-status-good" />
          <div>
            <p className="font-medium">Connected to {result.target_account}</p>
            <p className="text-muted-foreground">
              {result.regions.length} enabled regions. Scheduled scans are on — run the first one now.
            </p>
          </div>
        </div>
      ) : null}
      {result && !result.ok ? (
        <div role="alert" className="flex flex-col gap-1 rounded-lg border border-destructive/30 bg-destructive/5 px-3 py-2 text-sm">
          <p className="flex items-center gap-2 font-medium text-destructive">
            <CircleAlert aria-hidden className="size-4 shrink-0" />
            Failed while: {STAGE_LABEL[result.stage] ?? result.stage}
          </p>
          {result.error ? <p className="font-mono text-xs break-all">{result.error}</p> : null}
          {result.hint ? <p className="text-muted-foreground">{result.hint}</p> : null}
        </div>
      ) : null}
    </div>
  );
}

export function ScanButton({ id, disabled }: { id: string; disabled: boolean }) {
  const [state, action] = useActionState<FormState, FormData>(scanAccountAction.bind(null, id), {});
  return (
    <form action={action} className="flex flex-col gap-2">
      <div>
        <SubmitButton pendingLabel="Starting…" icon={<Play aria-hidden />} variant={disabled ? "outline" : "default"}>
          Scan now
        </SubmitButton>
      </div>
      <FormError error={state.error} />
    </form>
  );
}

export function ChangeRoleForm({ id, current }: { id: string; current: string }) {
  const [state, action] = useActionState<FormState, FormData>(changeRoleAction.bind(null, id), {});
  return (
    <form action={action} className="flex flex-col gap-2">
      <div className="flex flex-wrap items-end gap-2">
        <div className="min-w-64 flex-1">
          <Field label="IAM role name" hint="Must start with FinOps-ReadOnly. Changing it pauses scans until the new role is verified.">
            <input name="role_name" required maxLength={64} defaultValue={current} className={`${inputClass} font-mono`} />
          </Field>
        </div>
        <div className="pb-5">
          <SubmitButton pendingLabel="Saving…" variant="outline">
            Save
          </SubmitButton>
        </div>
      </div>
      <FormError error={state.error} />
    </form>
  );
}

export function DeleteAccountButton({ id, name }: { id: string; name: string }) {
  return (
    <form
      action={deleteAccountAction.bind(null, id)}
      onSubmit={(e) => {
        if (!confirm(`Remove ${name} and its findings from FinOps Tool? Nothing is changed in AWS.`)) e.preventDefault();
      }}
    >
      <SubmitButton pendingLabel="Removing…" variant="destructive" icon={<Trash2 aria-hidden />}>
        Remove account
      </SubmitButton>
    </form>
  );
}

/** Re-fetches server data every few seconds while a scan is running. */
export function AutoRefresh({ active, intervalMs = 4000 }: { active: boolean; intervalMs?: number }) {
  const router = useRouter();
  useEffect(() => {
    if (!active) return;
    const timer = setInterval(() => router.refresh(), intervalMs);
    return () => clearInterval(timer);
  }, [active, intervalMs, router]);
  return null;
}
