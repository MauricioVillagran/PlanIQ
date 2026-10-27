import type { Metadata, Viewport } from "next";
import type { ReactNode } from "react";

export const metadata: Metadata = {
  title: "PlanIQ",
  description: "Planificación productiva de planta",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: "#324664",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="es-CL">
      <body style={{ margin: 0, background: "#EDEDEB", color: "#324664", fontFamily: "system-ui, sans-serif" }}>
        {children}
      </body>
    </html>
  );
}
