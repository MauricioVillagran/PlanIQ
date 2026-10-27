"use client";

import { RequirePermission } from "@/components/layout/require-permission";
import { MaintainerPage } from "@/components/maintainer/maintainer-page";
import { plantsDefinition } from "@/features/plants/plants";
import { useAuth } from "@/lib/auth/auth-context";

export default function PlantsPage() {
  const { refreshMe } = useAuth();
  return (
    <RequirePermission permission={plantsDefinition.viewPermission}>
      {/* Las plantas del selector de contexto vienen de /auth/me: se recargan tras cada cambio. */}
      <MaintainerPage definition={plantsDefinition} onChanged={() => void refreshMe()} />
    </RequirePermission>
  );
}
