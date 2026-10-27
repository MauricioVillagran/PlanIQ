"use client";

import { useMemo } from "react";

import { RequirePermission } from "@/components/layout/require-permission";
import { MaintainerPage } from "@/components/maintainer/maintainer-page";
import { Alert } from "@/components/ui/feedback";
import { makeHoldingCagesDefinition } from "@/features/farms/farms";
import { useAppContext } from "@/lib/app-context";

/** Jaulas de acopio de la planta elegida en el selector de contexto. */
export default function HoldingCagesPage() {
  const { plant } = useAppContext();
  const definition = useMemo(() => makeHoldingCagesDefinition(plant), [plant]);
  return (
    <RequirePermission permission={definition.viewPermission}>
      {plant ? (
        <MaintainerPage key={plant.id} definition={definition} baseQuery={{ plant_id: plant.id }} />
      ) : (
        <Alert tone="info">Elija una planta en el selector superior para ver sus jaulas de acopio.</Alert>
      )}
    </RequirePermission>
  );
}
