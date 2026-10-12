"use client";

import { Menu } from "@base-ui/react/menu";
import { ChevronDown, LogOut } from "lucide-react";

function initials(name: string | null | undefined, email: string): string {
  const source = name?.trim() || email;
  const parts = source.split(/[\s@._-]+/).filter(Boolean);
  return ((parts[0]?.[0] ?? "") + (parts[1]?.[0] ?? "")).toUpperCase() || "?";
}

export function UserMenu({ email, name }: { email: string; name?: string | null }) {
  return (
    <Menu.Root>
      <Menu.Trigger
        className="flex shrink-0 items-center gap-2 rounded-md px-1.5 py-1 text-sm text-nav-muted outline-none transition-colors hover:bg-white/5 hover:text-nav-foreground focus-visible:ring-2 focus-visible:ring-primary data-popup-open:bg-white/10 data-popup-open:text-nav-foreground"
        aria-label="Account menu"
      >
        <span
          aria-hidden
          className="flex size-7 items-center justify-center rounded-full bg-white/10 text-xs font-semibold text-nav-foreground"
        >
          {initials(name, email)}
        </span>
        <span className="hidden max-w-48 truncate md:inline">{email}</span>
        <ChevronDown aria-hidden className="size-4" />
      </Menu.Trigger>
      <Menu.Portal>
        <Menu.Positioner sideOffset={8} align="end" className="z-50">
          <Menu.Popup className="min-w-56 rounded-lg border bg-popover p-1 text-sm text-popover-foreground shadow-lg outline-none">
            <div className="px-2.5 py-2">
              {name ? <p className="font-medium">{name}</p> : null}
              <p className="truncate text-xs text-muted-foreground">{email}</p>
            </div>
            <Menu.Separator className="my-1 h-px bg-border" />
            <Menu.LinkItem
              href="/signout"
              className="flex items-center gap-2 rounded-md px-2.5 py-1.5 outline-none data-highlighted:bg-muted"
            >
              <LogOut aria-hidden className="size-4 text-muted-foreground" />
              Sign out
            </Menu.LinkItem>
          </Menu.Popup>
        </Menu.Positioner>
      </Menu.Portal>
    </Menu.Root>
  );
}
