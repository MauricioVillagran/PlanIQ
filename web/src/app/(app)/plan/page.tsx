"use client";

import { RequirePermission } from "@/components/layout/require-permission";
import { PlanPage } from "@/features/plan/plan-page";

export default function HarvestPlanPage() {
  return (
    <RequirePermission permission="plan.view">
      <PlanPage />
    </RequirePermission>
  );
}
