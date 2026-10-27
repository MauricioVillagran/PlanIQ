import type { Metadata, Viewport } from "next";
import { DM_Mono, DM_Sans } from "next/font/google";
import type { ReactNode } from "react";

import { Providers } from "@/components/providers";

import "./globals.css";

// next/font descarga las fuentes al compilar y las sirve desde la propia app (sin CDN en ejecución).
const dmSans = DM_Sans({ subsets: ["latin"], weight: ["400", "500", "600", "700"], variable: "--font-dm-sans" });
const dmMono = DM_Mono({ subsets: ["latin"], weight: ["400", "500"], variable: "--font-dm-mono" });

export const metadata: Metadata = {
  title: { default: "PlanIQ", template: "%s · PlanIQ" },
  description: "Planificación productiva de planta",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: "#324664",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="es-CL" className={`${dmSans.variable} ${dmMono.variable}`}>
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
