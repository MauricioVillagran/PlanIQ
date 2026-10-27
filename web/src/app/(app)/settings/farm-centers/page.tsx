"use client";

import { RequirePermission } from "@/components/layout/require-permission";
import { MaintainerPage } from "@/components/maintainer/maintainer-page";
import { farmCentersDefinition } from "@/features/farms/farms";

export default function FarmCentersPage() {
  return (
    <RequirePermission permission={farmCentersDefinition.viewPermission}>
      <MaintainerPage definition={farmCentersDefinition} />
    </RequirePermission>
  );
}
