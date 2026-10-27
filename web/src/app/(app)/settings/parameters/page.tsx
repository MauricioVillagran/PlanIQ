"use client";

import { useMemo } from "react";

import { RequirePermission } from "@/components/layout/require-permission";
import { MaintainerPage } from "@/components/maintainer/maintainer-page";
import { makeParametersDefinition } from "@/features/parameters/parameters";
import { useAuth } from "@/lib/auth/auth-context";

export default function ParametersPage() {
  const { me } = useAuth();
  const plants = useMemo(() => me?.plants ?? [], [me]);
  const allPlants = me?.all_plants ?? false;
  const definition = useMemo(() => makeParametersDefinition(plants, allPlants), [plants, allPlants]);
  return (
    <RequirePermission permission={definition.viewPermission}>
      <MaintainerPage definition={definition} />
    </RequirePermission>
  );
}
