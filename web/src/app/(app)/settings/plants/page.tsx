"use client";

import { RequirePermission } from "@/components/layout/require-permission";
import { MaintainerPage } from "@/components/maintainer/maintainer-page";
import { plantsDefinition } from "@/features/plants/plants";

export default function PlantsPage() {
  return (
    <RequirePermission permission={plantsDefinition.viewPermission}>
      <MaintainerPage definition={plantsDefinition} />
    </RequirePermission>
  );
}
