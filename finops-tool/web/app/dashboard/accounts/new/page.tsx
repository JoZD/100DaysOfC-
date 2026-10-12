
import { AppShell } from "@/components/app/AppShell";
import { NewAccountForm } from "@/components/accounts/forms";
import { PageHeader, SectionCard } from "@/components/dashboard/primitives";
import { requireSession } from "@/lib/session";

// Must match services/common/aws_access.py DEFAULT_ROLE_NAME.
const DEFAULT_ROLE_NAME = "FinOps-ReadOnly";

export default async function NewAccountPage() {
  const session = await requireSession();
  const user = { email: session.email, name: null };

  return (
    <AppShell user={user} active="accounts">
      <PageHeader
        title="Connect an AWS account"
        description="Register the account, then create a read-only IAM role in it using the generated instructions."
      />
      <SectionCard
        title="Account details"
        description="Nothing is created in AWS by this form. The next page shows the exact role to create."
      >
        <NewAccountForm defaultRoleName={DEFAULT_ROLE_NAME} />
      </SectionCard>
    </AppShell>
  );
}
