import type { ReactNode } from "react";

import { Brand } from "@/components/brand";

export default function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <main className="flex min-h-dvh flex-col items-center justify-center px-4 py-8">
      <div className="w-full max-w-sm animate-fade-up">
        <div className="mb-6 flex flex-col items-center gap-1 text-center">
          <Brand />
          <p className="text-sm text-muted">Planificación productiva de planta</p>
        </div>
        {children}
      </div>
    </main>
  );
}
