import { defineConfig, devices } from "@playwright/test";

/**
 * Pruebas end-to-end de los criterios de aceptación. Corren contra un stack aislado y recién creado
 * (scripts/e2e.sh), nunca contra la base de desarrollo.
 *
 * 1. "primer-ingreso": el administrador inicial entra y cambia su contraseña (una sola vez).
 * 2. "escritorio" y "movil": el resto de los flujos, cada uno con sus propios datos, en 1280 px y 360 px.
 */
const baseURL = process.env.E2E_BASE_URL ?? "http://127.0.0.1:8090";

const desktop = { ...devices["Desktop Chrome"], viewport: { width: 1280, height: 800 } };
const mobile = {
  ...devices["Pixel 7"],
  viewport: { width: 360, height: 780 },
};

export default defineConfig({
  testDir: "./e2e",
  // Los flujos dependen del orden (se crean planta, turnos y usuarios en el camino).
  fullyParallel: false,
  workers: 1,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  timeout: 60_000,
  expect: { timeout: 10_000 },
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : [["list"]],
  use: {
    baseURL,
    locale: "es-CL",
    timezoneId: "America/Santiago",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    { name: "primer-ingreso", testMatch: /first-login\.setup\.ts/, use: desktop },
    { name: "escritorio", testMatch: /\.spec\.ts/, dependencies: ["primer-ingreso"], use: desktop },
    { name: "movil", testMatch: /\.spec\.ts/, dependencies: ["primer-ingreso"], use: mobile },
  ],
});
