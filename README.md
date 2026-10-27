# PlanIQ

Sistema web de planificación productiva para plantas de proceso de salmón: planificación de cosecha, simulación de graders, real versus plan, distribución comercial y seguimiento, usable en escritorio y celular.

- Alcance, arquitectura y fases: [docs/PROMPT_Sistema_Planificacion.md](docs/PROMPT_Sistema_Planificacion.md)
- Reglas permanentes del proyecto: [CLAUDE.md](CLAUDE.md)
- Decisiones de arquitectura: [docs/adr/](docs/adr/)
- Plan y entrega por fase: [docs/fases/](docs/fases/)

## Estado

Fase 0 (fundación y administración) en curso. Las instrucciones para levantar el entorno con Docker Desktop se completan al cerrar la fase.

## Estructura

```
api/      backend FastAPI
worker/   procesos en segundo plano (cargas Excel, sincronización Innova)
web/      frontend Next.js
infra/    Docker Compose y reverse proxy
docs/     especificación, ADR, manuales
```

## Datos

La carpeta `cargaExcel/` contiene archivos reales de producción y **no se versiona**. Copiar `.env.example` a `.env` y completar los valores; `.env` tampoco se versiona.

## Ramas

`main` (producción) ← `qa` ← `develop` ← `feature/<fase>-<tema>`. Todo cambio entra por pull request con el CI en verde.
