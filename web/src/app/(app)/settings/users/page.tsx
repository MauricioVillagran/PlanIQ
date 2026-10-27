"use client";

import { useMemo, useState } from "react";

import { RequirePermission } from "@/components/layout/require-permission";
import { MaintainerPage } from "@/components/maintainer/maintainer-page";
import { TemporaryPasswordDialog, makeUsersDefinition, type User } from "@/features/users/users";

export default function UsersPage() {
  const [created, setCreated] = useState<User | null>(null);
  const definition = useMemo(() => makeUsersDefinition(setCreated), []);
  return (
    <RequirePermission permission={definition.viewPermission}>
      <MaintainerPage definition={definition} />
      <TemporaryPasswordDialog
        username={created?.username ?? ""}
        password={created?.temporary_password ?? null}
        onClose={() => setCreated(null)}
      />
    </RequirePermission>
  );
}
