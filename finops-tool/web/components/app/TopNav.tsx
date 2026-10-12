import { UserMenu } from "@/components/app/UserMenu";

export type NavSection = "overview" | "accounts";

interface NavItem {
  label: string;
  href?: string;
  section?: NavSection;
}

// Findings is a section of the overview for now; Resources and Settings have
// no backing pages yet, so they render as "soon" instead of linking somewhere empty.
const NAV_ITEMS: NavItem[] = [
  { label: "Overview", href: "/dashboard", section: "overview" },
  { label: "Findings", href: "/dashboard#findings" },
  { label: "Accounts", href: "/dashboard/accounts", section: "accounts" },
  { label: "Resources" },
  { label: "Settings" },
];

function Logo() {
  return (
    <a
      href="/dashboard"
      aria-label="FinOps Tool overview"
      className="shrink-0 text-xl font-semibold tracking-tight text-nav-foreground"
    >
      FinOps Tool
    </a>
  );
}

export function TopNav({
  email,
  name,
  active = "overview",
}: {
  email: string;
  name?: string | null;
  active?: NavSection;
}) {
  return (
    <header className="sticky top-0 z-40 border-b border-nav-border bg-nav">
      <div className="mx-auto flex h-14 max-w-7xl items-center gap-8 px-4 sm:px-6">
        <Logo />
        <nav aria-label="Main" className="-mx-1 flex min-w-0 flex-1 items-center gap-1 overflow-x-auto">
          {NAV_ITEMS.map((item) => {
            const isActive = item.section === active;
            return item.href ? (
              <a
                key={item.label}
                href={item.href}
                aria-current={isActive ? "page" : undefined}
                className={
                  "relative shrink-0 rounded-md px-3 py-1.5 text-sm font-medium transition-colors " +
                  (isActive
                    ? "bg-white/10 text-nav-foreground"
                    : "text-nav-muted hover:bg-white/5 hover:text-nav-foreground")
                }
              >
                {item.label}
              </a>
            ) : (
              <span
                key={item.label}
                aria-disabled
                title="Coming soon"
                className="flex shrink-0 cursor-default items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-nav-muted/60"
              >
                {item.label}
                <span className="rounded-sm border border-nav-border px-1 text-[10px] uppercase tracking-wide">
                  Soon
                </span>
              </span>
            );
          })}
        </nav>
        <UserMenu email={email} name={name} />
      </div>
    </header>
  );
}
