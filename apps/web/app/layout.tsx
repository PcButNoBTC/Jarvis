import React from "react";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Luma — Only recommend what you observed",
  description:
    "Evidence-based opportunities, respectful outreach, and client-friendly briefs. Nothing sends without approval.",
  icons: {
    icon: [{ url: "/icon.svg", type: "image/svg+xml" }],
    shortcut: ["/favicon.svg"],
    apple: [{ url: "/icon.svg" }],
  },
  openGraph: {
    title: "Luma",
    description:
      "Self-hosted AI business operating system: research sites, map service opportunities, draft outreach, share client briefs.",
    type: "website",
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body
        style={{
          fontFamily:
            'ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, sans-serif',
          margin: 0,
          background: "#f8fafc",
        }}
      >
        {children}
      </body>
    </html>
  );
}
