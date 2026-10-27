"""Auditoría central con eventos de sesión de SQLAlchemy.

- `before_flush` completa `created_by` / `updated_by` con el usuario de la sesión.
- `after_flush` escribe en `core.audit_log` las diferencias campo a campo de cada objeto insertado,
  modificado o borrado (en ese momento los ids ya existen y el historial de atributos sigue disponible).

El usuario que actúa se guarda en `session.info["actor_id"]` (lo fija la autenticación). Se usa la sesión
y no una ContextVar porque FastAPI ejecuta dependencias y endpoints síncronos en hilos distintos.

Solo se audita lo que pasa por objetos del ORM. Las sentencias masivas (`update()`, `insert()` con
listas, cargas por staging) no generan eventos: se usan únicamente en tablas excluidas o en cargas
auditadas por lote (ADR 0001, decisión 3).
"""

import logging
from collections.abc import Iterable
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from sqlalchemy import event, insert
from sqlalchemy.orm import ColumnProperty, Session, UOWTransaction
from sqlalchemy.orm.attributes import History, instance_state

from app.core.logging import request_id_var
from app.modules.audit.models import AuditAction, AuditLog

logger = logging.getLogger(__name__)

ACTOR_KEY = "actor_id"
MASKED = "***"
# Columnas que cambian en toda escritura y no aportan a la auditoría.
_ALWAYS_EXCLUDED = frozenset({"row_version", "created_at", "created_by", "updated_at", "updated_by"})

_registered = False


def set_actor(session: Session, user_id: int | None) -> None:
    """Indica qué usuario realiza las escrituras de esta sesión (None = sistema)."""
    session.info[ACTOR_KEY] = user_id


def get_actor(session: Session) -> int | None:
    value = session.info.get(ACTOR_KEY)
    return value if isinstance(value, int) else None


def _is_audited(obj: object) -> bool:
    return bool(getattr(type(obj), "__audit__", True))


def _jsonable(value: Any) -> Any:
    if value is None or isinstance(value, bool | int | float | str):
        return value
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, bytes):
        return value.hex()
    if isinstance(value, dict | list):
        return value
    return str(value)


def _ref(obj: object) -> dict[str, Any]:
    """Referencia legible a un objeto relacionado: id y código o nombre si los tiene."""
    ref: dict[str, Any] = {"id": getattr(obj, "id", None)}
    for attr in ("code", "username", "name"):
        label = getattr(obj, attr, None)
        if isinstance(label, str):
            ref[attr] = label
            break
    return ref


def _first(values: Iterable[Any]) -> Any:
    return next(iter(values), None)


def _column_changes(obj: object, *, snapshot: bool) -> dict[str, Any]:
    """Diferencias de columnas. Con `snapshot` (alta o baja) registra todos los valores no nulos."""
    cls = type(obj)
    excluded = _ALWAYS_EXCLUDED | getattr(cls, "__audit_exclude__", frozenset())
    masked: frozenset[str] = getattr(cls, "__audit_mask__", frozenset())
    state = instance_state(obj)
    changes: dict[str, Any] = {}
    for prop in state.mapper.column_attrs:
        key = prop.key
        if key in excluded or not isinstance(prop, ColumnProperty):
            continue
        if snapshot:
            # Solo valores ya cargados: leer un atributo vencido dispararía una consulta dentro del flush.
            value = state.dict.get(key)
            if value is not None:
                changes[key] = {"new": MASKED if key in masked else _jsonable(value)}
            continue
        history: History = state.attrs[key].history
        if not history.has_changes():
            continue
        old, new = _first(history.deleted), _first(history.added)
        if old == new:
            continue
        if key in masked:
            changes[key] = {"old": MASKED, "new": MASKED}
        else:
            changes[key] = {"old": _jsonable(old), "new": _jsonable(new)}
    return changes


def _relationship_changes(obj: object) -> dict[str, Any]:
    state = instance_state(obj)
    excluded: frozenset[str] = getattr(type(obj), "__audit_exclude__", frozenset())
    changes: dict[str, Any] = {}
    for rel in state.mapper.relationships:
        if rel.key in excluded or rel.viewonly:
            continue
        history = state.attrs[rel.key].history
        added = [_ref(o) for o in history.added or () if o is not None]
        removed = [_ref(o) for o in history.deleted or () if o is not None]
        if added or removed:
            changes[rel.key] = {"added": added, "removed": removed}
    return changes


def _action_for_update(changes: dict[str, Any]) -> AuditAction:
    active = changes.get("is_active")
    if active is not None and set(active) == {"old", "new"}:
        if active["old"] is True and active["new"] is False:
            return AuditAction.DEACTIVATE
        if active["old"] is False and active["new"] is True:
            return AuditAction.ACTIVATE
    return AuditAction.UPDATE


def _plant_id(obj: object) -> int | None:
    if type(obj).__tablename__ == "plants":  # type: ignore[attr-defined]
        return getattr(obj, "id", None)
    value = getattr(obj, "plant_id", None)
    return value if isinstance(value, int) else None


def _entry(session: Session, obj: object, action: AuditAction, changes: dict[str, Any]) -> dict[str, Any]:
    table = type(obj).__table__  # type: ignore[attr-defined]
    return {
        "user_id": get_actor(session),
        "action": action.value,
        "entity": table.fullname,
        "entity_id": getattr(obj, "id"),  # noqa: B009 (todos los modelos auditados tienen id)
        "plant_id": _plant_id(obj),
        "changes": changes,
        "request_id": request_id_var.get(),
    }


def _before_flush(session: Session, _flush_context: UOWTransaction, _instances: object) -> None:
    actor = get_actor(session)
    if actor is None:
        return
    for obj in session.new:
        if hasattr(obj, "created_by") and getattr(obj, "created_by", None) is None:
            obj.created_by = actor
    for obj in session.dirty:
        if hasattr(obj, "updated_by") and session.is_modified(obj, include_collections=False):
            obj.updated_by = actor


def _after_flush(session: Session, _flush_context: UOWTransaction) -> None:
    rows: list[dict[str, Any]] = []
    for obj in session.new:
        if _is_audited(obj):
            changes = _column_changes(obj, snapshot=True) | _relationship_changes(obj)
            rows.append(_entry(session, obj, AuditAction.CREATE, changes))
    for obj in session.dirty:
        if not _is_audited(obj) or obj in session.deleted:
            continue
        changes = _column_changes(obj, snapshot=False) | _relationship_changes(obj)
        if changes:
            rows.append(_entry(session, obj, _action_for_update(changes), changes))
    for obj in session.deleted:
        if _is_audited(obj):
            rows.append(_entry(session, obj, AuditAction.DELETE, _column_changes(obj, snapshot=True)))
    if rows:
        session.connection().execute(insert(AuditLog), rows)


def register_audit_listeners() -> None:
    """Activa la auditoría para todas las sesiones del proceso. Idempotente."""
    global _registered
    if _registered:
        return
    event.listen(Session, "before_flush", _before_flush)
    event.listen(Session, "after_flush", _after_flush)
    _registered = True
