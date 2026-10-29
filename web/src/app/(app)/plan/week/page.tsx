"use client";

import { RequirePermission } from "@/components/layout/require-permission";
import { WeekPage } from "@/features/plan/week-page";

export default function HarvestWeekPage() {
  return (
    <RequirePermission permission="plan.view">
      <WeekPage />
    </RequirePermission>
  );
}
