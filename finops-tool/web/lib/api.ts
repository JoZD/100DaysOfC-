import { redirect } from "next/navigation";

// Server-only: every call happens in server components, so the browser never
// needs to reach the API. Read at request time (not inlined at build time like
// NEXT_PUBLIC_*), so one Docker image works in any environment.
function apiBaseUrl(): string {
  return process.env.API_BASE_URL ?? "http://localhost:8000";
}

export interface Finding {
  id: string;
  aws_account_id: string;
  aws_account_name: string;
  aws_account_number: string;
  resource_id: string;
  rule_id: string;
  category: string;
  monthly_savings_usd: number;
  remediation_effort: "low" | "medium" | "high";
  risk: "low" | "medium" | "high";
  evidence: Record<string, unknown>;
  remediation_action: string;
  detected_at: string;
}

export interface RuleSummary {
  rule_id: string;
  findings_count: number;
  monthly_savings_usd: number;
}

export type ScanStatus = "ok" | "failed" | "running" | null;

export interface AccountSummary {
  aws_account_id: string;
  aws_account_name: string;
  aws_account_number: string;
  scan_enabled: boolean;
  verified_at: string | null;
  last_scan_at: string | null;
  last_scan_status: ScanStatus;
  findings_count: number;
  monthly_savings_usd: number;
}

export interface Summary {
  findings_count: number;
  total_monthly_savings_usd: number;
  by_rule: RuleSummary[];
  by_account: AccountSummary[];
}

export class ApiError extends Error {
  constructor(
    public status: number,
    public detail: string,
  ) {
    super(`API ${status}: ${detail}`);
  }
}

export interface AwsAccount {
  id: string;
  name: string;
  role_arn: string;
  aws_account_number: string;
  scan_enabled: boolean;
  verified_at: string | null;
  last_scan_at: string | null;
  last_scan_status: ScanStatus;
  last_scan_error: string | null;
  created_at: string;
}

export interface SourceIdentityInfo {
  account_id: string;
  caller_arn: string;
  principal_arn: string | null;
  principal_arn_pattern: string | null;
}

export interface AccountSetup extends AwsAccount {
  role_name: string;
  external_id: string;
  source: SourceIdentityInfo | null;
  source_error: string | null;
  permissions_policy_name: string;
  trust_policy: Record<string, unknown>;
  permissions_policy: Record<string, unknown>;
  source_policy_statement: Record<string, unknown>;
}

export interface VerifyResult {
  ok: boolean;
  stage: "source" | "assume_role" | "identity" | "permissions" | "done";
  source_arn: string | null;
  target_account: string | null;
  regions: string[];
  error: string | null;
  hint: string | null;
}

// The backend derives the tenant from the signed-in user itself — see
// services/api/tenancy.py. This client never sends a tenant id.
async function apiRequest<T>(
  method: "GET" | "POST" | "PATCH" | "DELETE",
  path: string,
  accessToken: string | null,
  body?: unknown,
): Promise<T> {
  const res = await fetch(`${apiBaseUrl()}${path}`, {
    method,
    headers: {
      ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
      ...(body === undefined ? {} : { "Content-Type": "application/json" }),
    },
    body: body === undefined ? undefined : JSON.stringify(body),
    cache: "no-store",
  });

  // Expired session or deleted user: clear the cookie and sign in again.
  if (res.status === 401 && accessToken) redirect("/signout");

  if (!res.ok) {
    const text = await res.text();
    let detail = text;
    try {
      const parsed = JSON.parse(text).detail ?? text;
      // FastAPI validation errors are a list of {msg, loc}.
      detail = Array.isArray(parsed) ? parsed.map((e) => e.msg).join("; ") : String(parsed);
    } catch {}
    throw new ApiError(res.status, detail);
  }

  return res.status === 204 ? (undefined as T) : res.json();
}

export async function login(
  email: string,
  password: string,
): Promise<{ access_token: string; expires_at: string }> {
  return apiRequest("POST", "/auth/login", null, { email, password });
}

export function fetchFindings(accessToken: string): Promise<Finding[]> {
  return apiRequest<Finding[]>("GET", "/findings", accessToken);
}

export function fetchSummary(accessToken: string): Promise<Summary> {
  return apiRequest<Summary>("GET", "/summary", accessToken);
}

export function fetchAccounts(accessToken: string): Promise<AwsAccount[]> {
  return apiRequest<AwsAccount[]>("GET", "/accounts", accessToken);
}

export function fetchAccountSetup(accessToken: string, id: string): Promise<AccountSetup> {
  return apiRequest<AccountSetup>("GET", `/accounts/${encodeURIComponent(id)}`, accessToken);
}

export function createTenant(accessToken: string, name: string): Promise<{ id: string }> {
  return apiRequest("POST", "/tenant", accessToken, { name });
}

export function createAccount(
  accessToken: string,
  input: { name: string; account_number: string; role_name?: string },
): Promise<{ id: string }> {
  return apiRequest("POST", "/accounts", accessToken, input);
}

export function updateAccount(
  accessToken: string,
  id: string,
  input: { scan_enabled?: boolean; role_name?: string },
): Promise<AwsAccount> {
  return apiRequest("PATCH", `/accounts/${encodeURIComponent(id)}`, accessToken, input);
}

export function deleteAccount(accessToken: string, id: string): Promise<void> {
  return apiRequest("DELETE", `/accounts/${encodeURIComponent(id)}`, accessToken);
}

export function verifyAccount(accessToken: string, id: string): Promise<VerifyResult> {
  return apiRequest("POST", `/accounts/${encodeURIComponent(id)}/verify`, accessToken);
}

export function startScan(accessToken: string, id: string): Promise<{ status: string }> {
  return apiRequest("POST", `/accounts/${encodeURIComponent(id)}/scan`, accessToken);
}
