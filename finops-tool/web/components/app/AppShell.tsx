import type { ReactNode } from "react";

import { TopNav, type NavSection } from "@/components/app/TopNav";

export interface ViewUser {
  email: string;
  name?: string | null;
}

export function AppShell({
  user,
  active,
  children,
}: {
  user: ViewUser;
  active?: NavSection;
  children: ReactNode;
}) {
  return (
    <div className="min-h-screen bg-background">
      <TopNav email={user.email} name={user.name} active={active} />
      <main className="mx-auto flex max-w-7xl flex-col gap-6 px-4 py-8 sm:px-6">{children}</main>
    </div>
  );
}
