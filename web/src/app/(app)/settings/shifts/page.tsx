"use client";

import { useMemo } from "react";

import { RequirePermission } from "@/components/layout/require-permission";
import { MaintainerPage } from "@/components/maintainer/maintainer-page";
import { Alert } from "@/components/ui/feedback";
import { ShiftCoverage, makeShiftsDefinition } from "@/features/shifts/shifts";
import { useAppContext } from "@/lib/app-context";

/** Turnos de la planta elegida en el selector de contexto. */
export default function ShiftsPage() {
  const { plant } = useAppContext();
  const definition = useMemo(() => makeShiftsDefinition(plant), [plant]);
  return (
    <RequirePermission permission={definition.viewPermission}>
      {plant ? (
        <MaintainerPage
          key={plant.id}
          definition={definition}
          baseQuery={{ plant_id: plant.id }}
          header={<ShiftCoverage plantId={plant.id} />}
        />
      ) : (
        <Alert tone="info">Elija una planta en el selector superior para ver sus turnos.</Alert>
      )}
    </RequirePermission>
  );
}
