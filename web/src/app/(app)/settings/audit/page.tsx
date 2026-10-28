"use client";

import { RequirePermission } from "@/components/layout/require-permission";
import { AuditPage } from "@/features/audit/audit-page";

export default function AuditSettingsPage() {
  return (
    <RequirePermission permission="audit.view">
      <AuditPage />
    </RequirePermission>
  );
}
