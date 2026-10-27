import { expect, test } from "@playwright/test";

import { completePasswordChange, env, login } from "./helpers";

// Criterio: el administrador inicial entra y se le exige cambiar la contraseña.
test("el administrador inicial debe cambiar su contraseña en el primer ingreso", async ({ page }) => {
  await page.goto("/");
  await expect(page).toHaveURL(/\/login/);

  await login(page, env.adminUsername, env.adminInitialPassword);
  await expect(page.getByText("Por seguridad debe definir una contraseña propia")).toBeVisible();

  // Mientras no la cambie, el resto del sistema lo devuelve a esta pantalla.
  await page.goto("/settings");
  await expect(page).toHaveURL(/\/change-password/);

  // Tras cambiarla vuelve a donde quería ir.
  await completePasswordChange(page, env.adminInitialPassword, env.adminPassword);
  await expect(page).toHaveURL(/\/settings/);
  await expect(page.getByRole("heading", { name: "Configuración", level: 1 })).toBeVisible();
  // Base recién creada: ninguna planta precargada.
  await expect(page.getByText("Aún no hay plantas creadas.")).toBeVisible();

  // La clave inicial ya no sirve.
  await page.goto("/profile");
  await page.getByRole("button", { name: "Salir" }).filter({ visible: true }).first().click();
  await login(page, env.adminUsername, env.adminInitialPassword);
  await expect(page.getByRole("alert").filter({ hasText: "Usuario o contraseña incorrectos." })).toBeVisible();
});
