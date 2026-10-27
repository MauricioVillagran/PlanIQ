import { expect, type Locator, type Page, type TestInfo } from "@playwright/test";

function required(name: string): string {
  const value = process.env[name];
  if (!value) throw new Error(`Falta la variable de entorno ${name} (usar scripts/e2e.sh)`);
  return value;
}

export const env = {
  get adminUsername() {
    return process.env.E2E_ADMIN_USERNAME ?? "admin";
  },
  /** Clave inicial del administrador (INITIAL_ADMIN_PASSWORD). */
  get adminInitialPassword() {
    return required("E2E_ADMIN_PASSWORD");
  },
  /** Clave que el administrador define en su primer ingreso. */
  get adminPassword() {
    return required("E2E_ADMIN_NEW_PASSWORD");
  },
  /** Clave que define cada usuario creado en las pruebas. */
  get userPassword() {
    return required("E2E_USER_PASSWORD");
  },
};

export const isMobile = (testInfo: TestInfo) => testInfo.project.name === "movil";

/** Sufijo para que escritorio y celular creen datos distintos en la misma base. */
export const suffix = (testInfo: TestInfo) => (isMobile(testInfo) ? "m" : "e");

/** Elemento visible: tabla y tarjetas existen a la vez, solo una se muestra según el ancho. */
export const visible = (locator: Locator) => locator.filter({ visible: true }).first();

export async function login(page: Page, username: string, password: string): Promise<void> {
  await page.goto("/login");
  await page.getByLabel("Usuario").fill(username);
  await page.getByLabel("Contraseña").fill(password);
  await page.getByRole("button", { name: "Ingresar" }).click();
}

export async function loginAsAdmin(page: Page): Promise<void> {
  await login(page, env.adminUsername, env.adminPassword);
  await expect(page.getByRole("heading", { name: /^Hola/ })).toBeVisible();
}

/** Cambio de contraseña obligatorio del primer ingreso. */
export async function completePasswordChange(page: Page, current: string, next: string): Promise<void> {
  await expect(page).toHaveURL(/\/change-password/);
  await page.getByLabel(/Contraseña temporal|Contraseña actual/).fill(current);
  await page.getByLabel("Nueva contraseña", { exact: true }).fill(next);
  await page.getByLabel("Repetir nueva contraseña").fill(next);
  await page.getByRole("button", { name: "Guardar contraseña" }).click();
}

export async function expectToast(page: Page, text: string | RegExp): Promise<void> {
  await expect(page.getByRole("status").filter({ hasText: text })).toBeVisible();
}

/** Abre un mantenedor desde Configuración y espera el listado. */
export async function openSettings(page: Page, title: string): Promise<void> {
  await visible(page.getByRole("link", { name: "Configuración" })).click();
  await page.getByRole("link", { name: new RegExp(`^${title}`) }).click();
  await expect(page.getByRole("heading", { name: title, level: 1 })).toBeVisible();
}

/** Abre el registro (fila en escritorio, tarjeta en celular) por un texto visible. */
export async function openRow(page: Page, text: string): Promise<Locator> {
  await visible(page.getByText(text, { exact: true })).click();
  const panel = page.getByRole("dialog");
  await expect(panel).toBeVisible();
  return panel;
}
