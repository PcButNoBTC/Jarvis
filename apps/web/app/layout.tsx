import React from "react";

export const metadata = {
  title: "Luma — Only recommend what you observed",
  description:
    "Evidence-based opportunities, respectful outreach, and client-friendly briefs. Nothing sends without approval.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <head />
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
