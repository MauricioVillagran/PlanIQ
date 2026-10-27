// Regenera src/lib/api/schema.d.ts desde el OpenAPI de la API en ejecución.
// Uso: npm run api:types   (API_OPENAPI_URL cambia el origen; por defecto el proxy local)
import { execSync } from "node:child_process";

const url = process.env.API_OPENAPI_URL ?? "http://localhost:8080/api/v1/openapi.json";
if (!/^https?:\/\/[\w.:/-]+$/.test(url)) {
  throw new Error(`API_OPENAPI_URL inválida: ${url}`);
}
// Un solo comando como texto: en Windows npx es un .cmd y necesita shell.
execSync(`npx openapi-typescript ${url} -o src/lib/api/schema.d.ts`, { stdio: "inherit" });
