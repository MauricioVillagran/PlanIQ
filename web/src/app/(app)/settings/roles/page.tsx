"use client";

import { RequirePermission } from "@/components/layout/require-permission";
import { MaintainerPage } from "@/components/maintainer/maintainer-page";
import { rolesDefinition } from "@/features/roles/roles";

export default function RolesPage() {
  return (
    <RequirePermission permission={rolesDefinition.viewPermission}>
      <MaintainerPage definition={rolesDefinition} />
    </RequirePermission>
  );
}
