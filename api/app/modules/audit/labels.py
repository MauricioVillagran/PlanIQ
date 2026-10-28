"""Nombres en español para mostrar la auditoría (pantalla y Excel)."""

from typing import Any

# Tablas auditadas. Una tabla nueva sin entrada aquí se muestra con su nombre técnico.
ENTITY_LABELS: dict[str, str] = {
    "core.users": "Usuarios",
    "core.roles": "Roles",
    "master.plants": "Plantas",
    "master.shifts": "Turnos",
    "master.parameters": "Parámetros",
    "master.farm_centers": "Centros de cultivo",
    "master.cages": "Jaulas",
    "master.holding_cages": "Jaulas de acopio",
}

ACTION_LABELS: dict[str, str] = {
    "create": "Creación",
    "update": "Modificación",
    "deactivate": "Desactivación",
    "activate": "Activación",
    "delete": "Eliminación",
}


def entity_label(entity: str) -> str:
    return ENTITY_LABELS.get(entity, entity)


def _value(value: Any) -> str:
    if value is None or value == "":
        return "—"
    if value is True:
        return "Sí"
    if value is False:
        return "No"
    return str(value)


def _refs(items: Any) -> str:
    if not isinstance(items, list):
        return ""
    return ", ".join(str(i.get("code") or i.get("username") or i.get("name") or i.get("id")) for i in items)


def describe_changes(changes: dict[str, Any]) -> str:
    """Resumen en una línea: "name: Planta VS → Planta Victoria Sur; roles: + quality − planning"."""
    parts = []
    for field, change in changes.items():
        if field == "id" or not isinstance(change, dict):
            continue
        if "added" in change or "removed" in change:
            added, removed = _refs(change.get("added")), _refs(change.get("removed"))
            detail = " ".join(
                p for p in (f"+ {added}" if added else "", f"− {removed}" if removed else "") if p
            )
            parts.append(f"{field}: {detail}")
        elif "old" in change:
            parts.append(f"{field}: {_value(change['old'])} → {_value(change.get('new'))}")
        else:
            parts.append(f"{field}: {_value(change.get('new'))}")
    return "; ".join(parts)
