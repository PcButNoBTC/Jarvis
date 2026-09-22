import React from "react";

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return <html lang="en"><head><title>Luma</title></head><body style={{fontFamily:"system-ui",margin:0}}>{children}</body></html>;
}
