
import { ApiError, fetchFindings, fetchSummary } from "@/lib/api";
import { DashboardView, NotConnectedView } from "@/components/dashboard/DashboardView";
import { requireSession } from "@/lib/session";

export default async function DashboardPage({
  searchParams,
}: {
  searchParams: Promise<{ account?: string | string[] }>;
}) {
  const session = await requireSession();
  const accessToken = session.token;
  const user = { email: session.email, name: null };
  const { account } = await searchParams;
  const accountFilter = typeof account === "string" && account ? account : null;

  let summary, findings;
  try {
    [summary, findings] = await Promise.all([fetchSummary(accessToken), fetchFindings(accessToken)]);
  } catch (err) {
    // 403: token has no org; 404: org has no workspace yet. Both are setup
    // states the user resolves from the web, not crashes.
    if (err instanceof ApiError && (err.status === 404)) {
      return <NotConnectedView user={user} />;
    }
    throw err;
  }

  return <DashboardView user={user} summary={summary} findings={findings} accountFilter={accountFilter} />;
}
