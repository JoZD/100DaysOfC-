import { notFound } from "next/navigation";
import { ArrowLeft, CircleAlert, Pause, Play } from "lucide-react";

import { ApiError, fetchAccountSetup, type AccountSetup } from "@/lib/api";
import { setScanEnabledAction } from "@/app/dashboard/actions";
import { AppShell } from "@/components/app/AppShell";
import {
  AutoRefresh,
  ChangeRoleForm,
  DeleteAccountButton,
  ScanButton,
  VerifyPanel,
} from "@/components/accounts/forms";
import { AccountStatusPill, CodeBlock, Step, dateTime } from "@/components/accounts/shared";
import { Code, PageHeader, SectionCard } from "@/components/dashboard/primitives";
import { Button } from "@/components/ui/button";
import { requireSession } from "@/lib/session";

const json = (doc: unknown) => JSON.stringify(doc, null, 2);

function cliScript(s: AccountSetup): string {
  return `# Run in AWS account ${s.aws_account_number} as an identity allowed to manage IAM roles.
cat > finops-trust.json <<'EOF'
${json(s.trust_policy)}
EOF

cat > finops-permissions.json <<'EOF'
${json(s.permissions_policy)}
EOF

aws iam create-role \\
  --role-name ${s.role_name} \\
  --description "Read-only inventory access for FinOps Tool" \\
  --max-session-duration 3600 \\
  --assume-role-policy-document file://finops-trust.json

aws iam put-role-policy \\
  --role-name ${s.role_name} \\
  --policy-name ${s.permissions_policy_name} \\
  --policy-document file://finops-permissions.json

# Role already exists? Refresh its trust policy instead of create-role:
# aws iam update-assume-role-policy --role-name ${s.role_name} --policy-document file://finops-trust.json`;
}

function cloudFormation(s: AccountSetup): string {
  // JSON is valid YAML flow syntax, so the documents embed verbatim.
  return `AWSTemplateFormatVersion: "2010-09-09"
Description: Read-only inventory role for FinOps Tool
Resources:
  ReadOnlyRole:
    Type: AWS::IAM::Role
    Properties:
      RoleName: ${s.role_name}
      Description: Read-only inventory access for FinOps Tool
      MaxSessionDuration: 3600
      AssumeRolePolicyDocument: ${JSON.stringify(s.trust_policy)}
      Policies:
        - PolicyName: ${s.permissions_policy_name}
          PolicyDocument: ${JSON.stringify(s.permissions_policy)}
Outputs:
  RoleArn:
    Value: !GetAtt ReadOnlyRole.Arn`;
}

function Details({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <details className="group rounded-lg border">
      <summary className="cursor-pointer px-3 py-2 text-sm font-medium select-none group-open:border-b">{title}</summary>
      <div className="flex flex-col gap-3 px-3 py-3 text-sm">{children}</div>
    </details>
  );
}

export default async function AccountPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const session = await requireSession();
  const accessToken = session.token;
  const user = { email: session.email, name: null };

  let s: AccountSetup;
  try {
    s = await fetchAccountSetup(accessToken, id);
  } catch (err) {
    if (err instanceof ApiError && (err.status === 404 || err.status === 422)) notFound();
    throw err;
  }

  const verified = Boolean(s.verified_at);
  const running = s.last_scan_status === "running";
  const sso = Boolean(s.source?.principal_arn_pattern);
  const sourcePolicy = json({ Version: "2012-10-17", Statement: [s.source_policy_statement] });

  return (
    <AppShell user={user} active="accounts">
      <AutoRefresh active={running} />
      <a href="/dashboard/accounts" className="inline-flex w-fit items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
        <ArrowLeft aria-hidden className="size-4" />
        All accounts
      </a>
      <PageHeader
        title={s.name}
        description={
          <span className="inline-flex flex-wrap items-center gap-2">
            <span className="font-mono">{s.aws_account_number}</span>
            <AccountStatusPill account={s} />
          </span>
        }
      />

      {s.source === null ? (
        <p role="alert" className="flex items-start gap-2 rounded-lg border border-status-serious/40 bg-status-serious/5 px-4 py-3 text-sm">
          <CircleAlert aria-hidden className="mt-0.5 size-4 shrink-0 text-status-serious" />
          <span>
            This server has no usable AWS credentials right now ({s.source_error}), so the trust policy below
            shows placeholders. Fix the server identity (see docs/DEPLOY_DEBIAN.md §5) and reload.
          </span>
        </p>
      ) : null}

      <Step n={1} title={`Create the read-only role in account ${s.aws_account_number}`} done={verified}>
        <p className="text-sm text-muted-foreground">
          The role <Code>{s.role_name}</Code> trusts only this server&apos;s identity and requires the ExternalId below.
          It can only call {(s.permissions_policy.Statement as { Action: string[] }[])[0].Action.map((a, i) => (
            <span key={a}>
              {i > 0 ? ", " : ""}
              <Code>{a}</Code>
            </span>
          ))}
          . Nothing can be modified with it.
        </p>
        <dl className="grid gap-2 text-sm sm:grid-cols-[10rem_1fr]">
          <dt className="text-muted-foreground">Role ARN</dt>
          <dd className="font-mono text-xs break-all">{s.role_arn}</dd>
          <dt className="text-muted-foreground">ExternalId</dt>
          <dd className="font-mono text-xs break-all">{s.external_id}</dd>
          <dt className="text-muted-foreground">Trusted identity</dt>
          <dd className="font-mono text-xs break-all">
            {s.source ? (s.source.principal_arn ?? s.source.principal_arn_pattern) : "unavailable"}
          </dd>
        </dl>
        <CodeBlock label="Option A — AWS CLI (CloudShell works)" code={cliScript(s)} />
        <Details title="Option B — CloudFormation template">
          <p className="text-muted-foreground">
            Save as <Code>finops-role.yaml</Code> and deploy it in the target account (console or{" "}
            <Code>aws cloudformation deploy --template-file finops-role.yaml --stack-name finops-readonly --capabilities CAPABILITY_NAMED_IAM</Code>).
          </p>
          <CodeBlock label="finops-role.yaml" code={cloudFormation(s)} />
        </Details>
        <Details title="Option C — AWS console, step by step">
          <ol className="list-decimal space-y-1.5 pl-5">
            <li>Sign in to account <Code>{s.aws_account_number}</Code> and open IAM → Roles → Create role.</li>
            <li>Choose <b>Custom trust policy</b>, replace the editor contents with the trust policy below, then Next.</li>
            <li>Skip the managed-policy list (attach nothing), then Next.</li>
            <li>Role name: <Code>{s.role_name}</Code>. Create role.</li>
            <li>
              Open the role → Add permissions → Create inline policy → JSON, paste the permissions policy below, name it{" "}
              <Code>{s.permissions_policy_name}</Code>, and create it.
            </li>
          </ol>
          <CodeBlock label="Trust policy" code={json(s.trust_policy)} />
          <CodeBlock label="Permissions policy" code={json(s.permissions_policy)} />
        </Details>
      </Step>

      <Step n={2} title="Nothing to do on the FinOps Tool side" done={verified}>
        <p className="text-sm text-muted-foreground">
          {s.source ? (
            <>
              This server runs as <Code>{s.source.caller_arn}</Code>.{" "}
            </>
          ) : null}
          Its identity is set up once, for every customer, with only the permission below: it may assume roles named{" "}
          <Code>FinOps-ReadOnly*</Code>. It gets into this account only because the role above trusts it and requires this
          account&apos;s ExternalId.
          {sso ? " (IAM Identity Center: this statement belongs in the permission set, once.)" : ""}
        </p>
        <Details title="One-time policy of this server's identity">
          <CodeBlock label="Policy for this server's identity" code={sourcePolicy} />
        </Details>
      </Step>

      <Step n={3} title="Verify the connection" done={verified}>
        <p className="text-sm text-muted-foreground">
          Assumes the role with its ExternalId and lists the account&apos;s enabled regions. Read-only; a successful
          check turns on scheduled scans.
          {verified ? ` Last verified ${dateTime.format(new Date(s.verified_at!))} UTC.` : ""}
        </p>
        <VerifyPanel id={s.id} />
      </Step>

      <Step n={4} title="Scan" done={s.last_scan_status === "ok"}>
        <p className="text-sm text-muted-foreground">
          {running
            ? "Scanning every enabled region… this page refreshes on its own."
            : s.last_scan_at
              ? `Last scan ${s.last_scan_status === "failed" ? "failed" : "succeeded"} at ${dateTime.format(new Date(s.last_scan_at))} UTC.`
              : "No scan yet. Scheduled scans also run automatically once verified."}
        </p>
        {s.last_scan_status === "failed" && s.last_scan_error ? (
          <p className="rounded-lg border border-destructive/30 bg-destructive/5 px-3 py-2 font-mono text-xs break-all text-destructive">
            {s.last_scan_error}
          </p>
        ) : null}
        <div className="flex flex-wrap items-start gap-2">
          {verified && !running ? <ScanButton id={s.id} disabled={false} /> : null}
          {s.last_scan_status === "ok" ? (
            <Button variant="outline" size="lg" nativeButton={false} render={<a href={`/dashboard?account=${s.aws_account_number}`} />}>
              View findings
            </Button>
          ) : null}
        </div>
      </Step>

      <SectionCard title="Settings" description="Changes here only affect FinOps Tool; nothing is modified in AWS.">
        <div className="flex flex-col gap-5">
          {verified ? (
            <form action={setScanEnabledAction.bind(null, s.id, !s.scan_enabled)} className="flex flex-wrap items-center gap-3">
              <Button type="submit" variant="outline" size="lg">
                {s.scan_enabled ? <Pause aria-hidden /> : <Play aria-hidden />}
                {s.scan_enabled ? "Pause scheduled scans" : "Resume scheduled scans"}
              </Button>
              <span className="text-sm text-muted-foreground">
                Scheduled scans are {s.scan_enabled ? "on" : "paused"}.
              </span>
            </form>
          ) : null}
          <ChangeRoleForm id={s.id} current={s.role_name} />
          <div className="border-t pt-4">
            <DeleteAccountButton id={s.id} name={s.name} />
            <p className="mt-2 text-xs text-muted-foreground">
              Removes the account and its findings here. Delete the IAM role in AWS separately if you no longer need it.
            </p>
          </div>
        </div>
      </SectionCard>
    </AppShell>
  );
}
