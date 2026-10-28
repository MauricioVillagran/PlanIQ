/**
 * Criterios de aceptación de la Fase 0 (sección 14), en 360 px y en escritorio.
 * Los pasos van en orden: cada uno usa lo que creó el anterior.
 */
import { expect, test, type Browser, type Page, type TestInfo } from "@playwright/test";

import {
  completePasswordChange,
  env,
  expectToast,
  isMobile,
  login,
  loginAsAdmin,
  openRow,
  openSettings,
  suffix,
  visible,
} from "./helpers";

test.describe.configure({ mode: "serial" });

type RoleCase = { role: string; key: string; seesUsers: boolean; canEditMasters: boolean };

const ROLES: RoleCase[] = [
  { role: "Planificación", key: "planificacion", seesUsers: false, canEditMasters: false },
  { role: "Producción / Frigorífico", key: "produccion", seesUsers: false, canEditMasters: false },
  { role: "Calidad", key: "calidad", seesUsers: false, canEditMasters: false },
  { role: "Control de Gestión / Admin", key: "admin", seesUsers: true, canEditMasters: true },
];

const plantFor = (info: TestInfo) =>
  isMobile(info)
    ? { code: "VSM", name: "Planta Victoria Sur Móvil" }
    : { code: "VS", name: "Planta Victoria Sur" };

const usernameFor = (info: TestInfo, key: string) => `e2e.${key}.${suffix(info)}`;

/** Claves temporales de los usuarios creados, para el paso siguiente. */
const temporaryPasswords = new Map<string, string>();

/** Otra sesión independiente (otro usuario), con el mismo tamaño de pantalla del proyecto. */
async function newPage(browser: Browser, info: TestInfo): Promise<Page> {
  const { viewport, userAgent, deviceScaleFactor, isMobile: mobile, hasTouch, locale, timezoneId, baseURL } =
    info.project.use;
  const context = await browser.newContext({
    viewport,
    userAgent,
    deviceScaleFactor,
    isMobile: mobile,
    hasTouch,
    locale,
    timezoneId,
    baseURL,
  });
  return context.newPage();
}

test("crea la planta y sus turnos día y noche (cruza medianoche)", async ({ page }, info) => {
  const plant = plantFor(info);
  await loginAsAdmin(page);

  await openSettings(page, "Plantas");
  await page.getByRole("button", { name: "Nueva planta" }).first().click();
  const panel = page.getByRole("dialog");
  await panel.getByLabel("Código").fill(plant.code);
  await panel.getByLabel("Nombre").fill(plant.name);
  await panel.getByLabel("Ubicación").fill("Puerto Montt");
  await panel.getByRole("button", { name: "Crear" }).click();
  await expectToast(page, `Registro creado: ${plant.code} · ${plant.name}`);
  await expect(visible(page.getByText(plant.name, { exact: true }))).toBeVisible();

  // Un código repetido se rechaza con el mensaje de la API bajo el campo.
  await page.getByRole("button", { name: "Nueva planta" }).first().click();
  await panel.getByLabel("Código").fill(plant.code);
  await panel.getByLabel("Nombre").fill("Duplicada");
  await panel.getByRole("button", { name: "Crear" }).click();
  await expect(panel.getByText("Ya existe planta con ese código.")).toBeVisible();
  await panel.getByRole("button", { name: "Cancelar" }).click();

  // La planta nueva aparece en el selector de contexto sin volver a ingresar.
  await page.getByRole("combobox", { name: "Planta" }).selectOption({ label: plant.name });
  await openSettings(page, "Turnos");

  for (const [name, start, end] of [
    ["Día", "08:00", "20:00"],
    ["Noche", "20:00", "08:00"],
  ] as const) {
    await page.getByRole("button", { name: "Nuevo turno" }).first().click();
    await expect(panel.getByText(`Planta: ${plant.name}`)).toBeVisible();
    await panel.getByLabel("Nombre").fill(name);
    await panel.getByLabel("Inicio").fill(start);
    await panel.getByLabel("Término").fill(end);
    if (name === "Noche") await expect(panel.getByText("El turno cruza la medianoche")).toBeVisible();
    await panel.getByRole("button", { name: "Crear" }).click();
    await expectToast(page, `Registro creado: Turno ${name}`);
  }
  await expect(page.getByText("Los turnos cubren las 24 horas")).toBeVisible();

  // Un turno que se traslapa se rechaza indicando con cuál.
  await page.getByRole("button", { name: "Nuevo turno" }).first().click();
  await panel.getByLabel("Nombre").fill("Madrugada");
  await panel.getByLabel("Inicio").fill("06:00");
  await panel.getByLabel("Término").fill("10:00");
  await panel.getByRole("button", { name: "Crear" }).click();
  await expect(panel.getByText(/se traslapa con: Día, Noche|se traslapa con: Noche, Día/)).toBeVisible();
});

test("crea un usuario de cada rol con acceso a la planta", async ({ page }, info) => {
  const plant = plantFor(info);
  await loginAsAdmin(page);
  await openSettings(page, "Usuarios");

  for (const { role, key } of ROLES) {
    const username = usernameFor(info, key);
    await page.getByRole("button", { name: "Nuevo usuario" }).first().click();
    const panel = page.getByRole("dialog");
    await panel.getByLabel("Usuario").fill(username);
    await panel.getByLabel("Nombre completo").fill(`E2E ${role}`);
    await panel.getByLabel("Correo").fill(`${username}@example.com`);
    await panel.getByLabel(role, { exact: true }).check();
    await panel.getByLabel(`${plant.code} · ${plant.name}`).check();
    await panel.getByRole("button", { name: "Crear" }).click();

    const dialog = page.getByRole("alertdialog", { name: "Clave temporal" });
    await expect(dialog).toBeVisible();
    const temporary = (await dialog.getByTestId("temporary-password").textContent())?.trim() ?? "";
    expect(temporary).toMatch(/^[A-Za-z0-9]{12,}$/);
    temporaryPasswords.set(username, temporary);
    await dialog.getByRole("button", { name: "Listo" }).click();
  }
  for (const { key } of ROLES) {
    await expect(visible(page.getByText(usernameFor(info, key), { exact: true }))).toBeVisible();
  }
});

test("cada usuario cambia su clave temporal y ve solo lo que su rol permite", async ({ browser }, info) => {
  const plant = plantFor(info);
  for (const { key, seesUsers, canEditMasters } of ROLES) {
    const username = usernameFor(info, key);
    const page = await newPage(browser, info);
    await login(page, username, temporaryPasswords.get(username) ?? "");
    await completePasswordChange(page, temporaryPasswords.get(username) ?? "", env.userPassword);
    await expect(page.getByRole("heading", { name: /^Hola/ })).toBeVisible();
    await expect(page.getByRole("combobox", { name: "Planta" })).toContainText(plant.name);

    await visible(page.getByRole("link", { name: "Configuración" })).click();
    await expect(page.getByRole("link", { name: /^Plantas/ })).toBeVisible();
    await expect(page.getByRole("link", { name: /^Usuarios/ })).toHaveCount(seesUsers ? 1 : 0);

    await page.getByRole("link", { name: /^Plantas/ }).click();
    await expect(visible(page.getByText(plant.name, { exact: true }))).toBeVisible();
    await expect(page.getByRole("button", { name: "Nueva planta" })).toHaveCount(canEditMasters ? 1 : 0);

    // Entrar directo a una sección sin permiso muestra "Sin acceso" (y la API responde 403).
    if (!seesUsers) {
      await page.goto("/settings/users");
      await expect(page.getByText("Sin acceso")).toBeVisible();
    }
    await page.context().close();
  }
});

test("cinco intentos fallidos bloquean la cuenta y el administrador la desbloquea", async ({ page, browser }, info) => {
  const username = usernameFor(info, "planificacion");
  const user = await newPage(browser, info);
  // Next agrega su propio role="alert" (anunciador de rutas): se busca la alerta por su texto.
  const formAlert = (text: string) => user.getByRole("alert").filter({ hasText: text });
  for (let attempt = 1; attempt <= 5; attempt++) {
    await login(user, username, "clave-incorrecta");
    await expect(formAlert(attempt < 5 ? "Usuario o contraseña incorrectos." : "La cuenta está bloqueada")).toBeVisible();
  }
  // Bloqueada: ni la contraseña correcta permite entrar.
  await login(user, username, env.userPassword);
  await expect(formAlert("La cuenta está bloqueada")).toBeVisible();

  await loginAsAdmin(page);
  await openSettings(page, "Usuarios");
  await page.getByPlaceholder("Buscar por usuario, nombre o correo").fill(username);
  const panel = await openRow(page, "E2E Planificación");
  await expect(panel.getByText("Cuenta bloqueada por intentos fallidos")).toBeVisible();
  await panel.getByRole("button", { name: "Desbloquear" }).click();
  await expectToast(page, "Usuario desbloqueado.");

  await login(user, username, env.userPassword);
  await expect(user.getByRole("heading", { name: /^Hola/ })).toBeVisible();
  await user.context().close();
});

test("todo cambio queda en el historial del registro", async ({ page }, info) => {
  const plant = plantFor(info);
  await loginAsAdmin(page);
  await openSettings(page, "Plantas");
  const panel = await openRow(page, plant.name);
  await panel.getByLabel("Ubicación").fill("Calbuco");
  await page.getByRole("button", { name: "Guardar cambios" }).click();
  await expectToast(page, "Cambios guardados.");

  await panel.getByRole("tab", { name: "Historial" }).click();
  const latest = panel.getByRole("listitem").first();
  await expect(latest).toContainText("Modificó");
  await expect(latest).toContainText("Ubicación");
  await expect(latest).toContainText("Calbuco");
  await expect(panel.getByText("Creó")).toBeVisible();
});

test("la auditoría muestra el cambio y se filtra por tabla y acción", async ({ page }, info) => {
  await loginAsAdmin(page);
  await openSettings(page, "Auditoría");
  await page.getByLabel("Tabla").selectOption({ label: "Plantas" });
  await page.getByLabel("Acción").selectOption({ label: "Modificación" });

  // La fila (escritorio) o la tarjeta (celular) del cambio de ubicación del paso anterior.
  const entries = isMobile(info) ? page.getByRole("listitem") : page.getByRole("row");
  const entry = visible(entries.filter({ hasText: "Calbuco" }));
  await expect(entry).toContainText("Plantas");
  await entry.click();
  const panel = page.getByRole("dialog");
  await expect(panel).toContainText("Modificación");
  await expect(panel).toContainText("Ubicación");
  await expect(panel).toContainText("Calbuco");
  await expect(panel).not.toContainText("Creación");
  await panel.getByRole("button", { name: "Cerrar", exact: true }).click();

  await page.getByLabel("Acción").selectOption({ label: "Creación" });
  await expect(entries.filter({ hasText: "Calbuco", visible: true })).toHaveCount(0);
});

test("sin scroll horizontal y con objetivos táctiles de 44 px", async ({ page }, info) => {
  test.skip(!isMobile(info), "Solo en 360 px");
  await loginAsAdmin(page);
  for (const title of ["Usuarios", "Roles y permisos", "Plantas", "Turnos", "Parámetros", "Auditoría"]) {
    await openSettings(page, title);
    // Medir con la página quieta: las animaciones de entrada mueven los elementos.
    // Solo las finitas (spinners y esqueletos giran para siempre); una cancelada no es un error.
    await page.evaluate(() =>
      Promise.all(
        document
          .getAnimations()
          .filter((a) => a.effect?.getTiming().iterations !== Infinity)
          .map((a) => a.finished.catch(() => undefined)),
      ),
    );
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    expect(overflow, `scroll horizontal en ${title}`).toBeLessThanOrEqual(0);
    const small = await page.evaluate(() =>
      [...document.querySelectorAll<HTMLElement>("button, a, select, input")]
        .filter((el) => {
          const r = el.getBoundingClientRect();
          // Medio píxel de tolerancia: con densidad fraccionaria, 44 px puede medirse como 43,99.
          return r.width > 0 && r.height > 0 && r.height < 43.5;
        })
        .map((el) => {
          const name = el.getAttribute("aria-label") || el.textContent?.trim() || el.getAttribute("placeholder");
          const type = el.getAttribute("type");
          const height = el.getBoundingClientRect().height.toFixed(1);
          return `${el.tagName.toLowerCase()}${type ? `[${type}]` : ""} "${name ?? ""}" ${height}px`;
        }),
    );
    expect(small, `objetivos táctiles chicos en ${title}`).toEqual([]);
  }
});
