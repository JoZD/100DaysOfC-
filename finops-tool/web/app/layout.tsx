import type { ReactNode } from "react";

import "./globals.css";

export const metadata = {
  title: "FinOps Tool",
  description: "FinOps findings for your AWS accounts",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" className="font-sans">
      {/* suppressHydrationWarning: browser extensions (e.g. ColorZilla) inject
          attributes into <body> before React hydrates, causing a false-positive
          hydration mismatch. Only suppresses attribute diffs on this element. */}
      <body suppressHydrationWarning>{children}</body>
    </html>
  );
}
