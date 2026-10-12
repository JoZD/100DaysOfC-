"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";

import {
  ApiError,
  createAccount,
  createTenant,
  deleteAccount,
  startScan,
  updateAccount,
  verifyAccount,
  type VerifyResult,
} from "@/lib/api";
import { requireSession } from "@/lib/session";

// Server actions: the access token never reaches the browser. The API derives
// the tenant from the signed-in user, so no action accepts a tenant id.

export interface FormState {
  error?: string;
}

async function token(): Promise<string> {
  return (await requireSession()).token;
}

function field(form: FormData, name: string): string {
  return String(form.get(name) ?? "").trim();
}

function message(err: unknown): string {
  if (err instanceof ApiError) return err.detail;
  throw err;
}

export async function createWorkspaceAction(_prev: FormState, form: FormData): Promise<FormState> {
  try {
    await createTenant(await token(), field(form, "name"));
  } catch (err) {
    return { error: message(err) };
  }
  redirect("/dashboard/accounts/new");
}

export async function createAccountAction(_prev: FormState, form: FormData): Promise<FormState> {
  let id: string;
  try {
    const roleName = field(form, "role_name");
    ({ id } = await createAccount(await token(), {
      name: field(form, "name"),
      account_number: field(form, "account_number").replace(/\D/g, ""),
      ...(roleName ? { role_name: roleName } : {}),
    }));
  } catch (err) {
    return { error: message(err) };
  }
  redirect(`/dashboard/accounts/${id}`);
}

export type VerifyState = { result?: VerifyResult; error?: string };

export async function verifyAccountAction(id: string, _prev: VerifyState): Promise<VerifyState> {
  try {
    const result = await verifyAccount(await token(), id);
    revalidatePath("/dashboard", "layout");
    return { result };
  } catch (err) {
    return { error: message(err) };
  }
}

export async function scanAccountAction(id: string, _prev: FormState): Promise<FormState> {
  try {
    await startScan(await token(), id);
  } catch (err) {
    return { error: message(err) };
  }
  revalidatePath("/dashboard", "layout");
  return {};
}

export async function setScanEnabledAction(id: string, enabled: boolean): Promise<void> {
  await updateAccount(await token(), id, { scan_enabled: enabled });
  revalidatePath("/dashboard", "layout");
}

export async function changeRoleAction(id: string, _prev: FormState, form: FormData): Promise<FormState> {
  try {
    await updateAccount(await token(), id, { role_name: field(form, "role_name") });
  } catch (err) {
    return { error: message(err) };
  }
  revalidatePath("/dashboard", "layout");
  return {};
}

export async function deleteAccountAction(id: string): Promise<void> {
  await deleteAccount(await token(), id);
  revalidatePath("/dashboard", "layout");
  redirect("/dashboard/accounts");
}
