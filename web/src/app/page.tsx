// Página provisoria de F0.2: confirma que web llega a la API y la API a SQL Server.
// F0.8 la reemplaza por el layout real con Tailwind y la paleta.

export const dynamic = "force-dynamic";

type Readiness = { ok: boolean; detail: string };

async function checkApi(): Promise<Readiness> {
  const baseUrl = process.env.API_INTERNAL_URL ?? "http://api:8000";
  try {
    const res = await fetch(`${baseUrl}/api/v1/health/ready`, { cache: "no-store" });
    const body = (await res.json()) as { database?: string; sqlserver_version?: string };
    return res.ok
      ? { ok: true, detail: `API y base de datos operativas (SQL Server ${body.sqlserver_version ?? "?"})` }
      : { ok: false, detail: `La API responde, pero la base de datos no (${body.database ?? res.status})` };
  } catch {
    return { ok: false, detail: "No se pudo contactar la API" };
  }
}

export default async function Home() {
  const status = await checkApi();
  return (
    <main style={{ maxWidth: 640, margin: "0 auto", padding: 16 }}>
      <h1 style={{ fontSize: 28, marginBottom: 4 }}>PlanIQ</h1>
      <p style={{ marginTop: 0 }}>Planificación productiva de planta · entorno en construcción (Fase 0)</p>
      <div
        style={{
          background: "#FFFFFF",
          borderRadius: 8,
          padding: 16,
          borderLeft: `6px solid ${status.ok ? "#0096A0" : "#FA6E5A"}`,
        }}
      >
        <strong>{status.ok ? "Infraestructura operativa" : "Infraestructura con problemas"}</strong>
        <p style={{ marginBottom: 0 }}>{status.detail}</p>
      </div>
    </main>
  );
}
