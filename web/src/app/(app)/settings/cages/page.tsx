"use client";

import { useQuery } from "@tanstack/react-query";
import { useMemo } from "react";

import { RequirePermission } from "@/components/layout/require-permission";
import { MaintainerPage } from "@/components/maintainer/maintainer-page";
import type { Page } from "@/components/maintainer/types";
import { Skeleton } from "@/components/ui/feedback";
import { makeCagesDefinition, type FarmCenter } from "@/features/farms/farms";
import { request } from "@/lib/api/client";

export default function CagesPage() {
  // Centros activos: para el filtro y para elegir el centro de una jaula nueva.
  const centers = useQuery({
    queryKey: ["farm-centers", "options"],
    queryFn: async () =>
      (
        await request<Page<FarmCenter>>("GET", "/api/v1/farm-centers", {
          query: { status: "active", sort: "code", page_size: 200 },
        })
      ).items,
  });
  const definition = useMemo(() => makeCagesDefinition(centers.data ?? []), [centers.data]);
  return (
    <RequirePermission permission={definition.viewPermission}>
      {centers.isPending ? (
        <Skeleton className="h-40" />
      ) : (
        <MaintainerPage
          definition={definition}
          createDisabledReason={centers.data?.length ? undefined : "Primero cree un centro de cultivo."}
        />
      )}
    </RequirePermission>
  );
}
