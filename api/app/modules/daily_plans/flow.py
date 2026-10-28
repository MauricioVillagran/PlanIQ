"""Flujo del plan diario: Borrador → Publicado → Cerrado, con versiones (sección 6, ADR 0005).

- Publicar crea la versión 1. Exige al menos una línea y ningún error bloqueante.
- Un plan publicado se modifica con un lote de cambios y un motivo: una versión nueva por lote.
- Cerrar solo se permite cuando terminó la fecha productiva; un plan cerrado es inmutable.
- Cada versión se reconstruye desde las tablas temporales con su `snapshot_at`.
"""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select

from app.core.errors import BusinessRuleError, ConflictError, NotFoundError
from app.domain import harvest
from app.domain.harvest import HarvestLine
from app.modules.daily_plans import repository
from app.modules.daily_plans.models import DailyPlan, DailyPlanVersion, HarvestEntry, PlanStatus, VersionKind
from app.modules.daily_plans.schemas import (
    DailyPlanOut,
    FieldChangeOut,
    HarvestEntryOut,
    LineChangeOut,
    PlanChangesIn,
    PlanLineOut,
    VersionCompareOut,
    VersionDetailOut,
    VersionOut,
)
from app.modules.daily_plans.service import DailyPlanService, issue_out, totals_out
from app.modules.users.models import User


def line_out(line: HarvestLine) -> PlanLineOut:
    return PlanLineOut(
        entry_id=int(line.key),
        sequence=line.order,
        farm_center_code=line.farm_center_code,
        cage_code=line.cage_code,
        holding_cage_code=line.holding_cage_code,
        shift_name=line.shift_name,
        fish_count=line.fish_count,
        avg_weight_kg=line.avg_weight_kg,
        biomass_kg=line.biomass_kg,
        notes=line.notes,
    )


def _plain(value: Any) -> str | int | None:
    if isinstance(value, Decimal):
        return format(value, "f")
    return value  # type: ignore[no-any-return]


class PlanFlowService(DailyPlanService):
    # Comunes -----------------------------------------------------------------------------

    def _check_version(self, plan: DailyPlan, row_version: str) -> None:
        if plan.row_version.hex() != row_version:
            raise ConflictError(
                details={"current": DailyPlanOut.model_validate(plan).model_dump(mode="json")}
            )

    def _block_errors(self, lines: list[HarvestLine], plan: DailyPlan, message: str) -> None:
        rules = self.rules(plan)
        issues = harvest.validate(lines, rules.holding_cages, rules.weight_range, rules.wfe_factor)
        errors = [i for i in issues if i.severity is harvest.Severity.ERROR]
        if errors:
            raise BusinessRuleError(
                f"{message} {errors[0].message}",
                code="plan_has_errors",
                details={"issues": [issue_out(i).model_dump() for i in errors]},
            )

    def _new_version(self, plan: DailyPlan, kind: VersionKind, reason: str | None) -> DailyPlanVersion:
        """Sube la versión del plan y guarda la cabecera en la misma transacción que los cambios."""
        plan.current_version += 1
        self.session.flush()  # primero las líneas y el plan: snapshot_at debe quedar después
        version = DailyPlanVersion(
            plant_id=plan.plant_id,
            daily_plan_id=plan.id,
            number=plan.current_version,
            kind=kind,
            reason=reason,
        )
        self.session.add(version)
        return version

    # Publicar ----------------------------------------------------------------------------

    def publish(self, plan_id: int, row_version: str) -> DailyPlan:
        plan = self.get(plan_id)
        if plan.status == PlanStatus.CLOSED:
            raise BusinessRuleError("El plan está cerrado.", code="plan_closed")
        if plan.status == PlanStatus.PUBLISHED:
            raise BusinessRuleError("El plan ya está publicado.", code="plan_already_published")
        self._check_version(plan, row_version)
        if not plan.entries:
            raise BusinessRuleError("El plan no tiene líneas de cosecha.", code="plan_empty")
        self._block_errors(repository.to_lines(plan.entries), plan, "No se puede publicar:")

        plan.status = PlanStatus.PUBLISHED
        plan.published_at = datetime.now(UTC)
        plan.published_by = self.user.id
        self._new_version(plan, VersionKind.PUBLISH, None)
        self.session.commit()
        return plan

    # Cambios con motivo sobre un plan publicado ---------------------------------------------

    def apply_changes(self, plan_id: int, data: PlanChangesIn) -> DailyPlan:
        plan = self.get(plan_id)
        if plan.status == PlanStatus.CLOSED:
            raise BusinessRuleError("El plan está cerrado y no se puede modificar.", code="plan_closed")
        if plan.status == PlanStatus.DRAFT:
            raise BusinessRuleError(
                "El plan está en Borrador: las líneas se editan directamente.", code="plan_not_published"
            )
        self._check_version(plan, data.row_version)

        entries = {e.id: e for e in plan.entries}
        before = repository.to_lines(plan.entries)

        def existing(entry_id: int, row_version: str) -> HarvestEntry:
            entry = entries.get(entry_id)
            if entry is None:
                raise NotFoundError(f"La línea {entry_id} no existe en el plan.", code="entry_not_found")
            if entry.row_version.hex() != row_version:
                raise ConflictError(
                    details={"current": HarvestEntryOut.model_validate(entry).model_dump(mode="json")}
                )
            return entry

        deleted = {existing(ref.id, ref.row_version).id for ref in data.delete}

        # Valores resultantes de cada línea que queda, y las nuevas.
        candidates: dict[int | str, tuple[dict[str, Any], Any]] = {}
        for entry in plan.entries:
            if entry.id not in deleted:
                values: dict[str, Any] = {
                    "cage_id": entry.cage_id,
                    "holding_cage_id": entry.holding_cage_id,
                    "shift_id": entry.shift_id,
                    "fish_count": entry.fish_count,
                    "avg_weight_kg": entry.avg_weight_kg,
                    "notes": entry.notes,
                }
                candidates[entry.id] = (values, entry.sequence)
        for change in data.update:
            if change.id in deleted:
                raise BusinessRuleError(
                    f"La línea {change.id} se modifica y se elimina a la vez.", code="invalid_changes"
                )
            existing(change.id, change.row_version)
            values, _ = candidates[change.id]
            updates = change.model_dump(exclude_unset=True, exclude={"id", "row_version"})
            values.update({k: v for k, v in updates.items() if v is not None or k == "notes"})
        last = max((seq for _, seq in candidates.values()), default=0)
        for index, new in enumerate(data.add):
            candidates[f"new-{index}"] = (new.model_dump(), last + index + 1)

        # Orden de faena resultante: el enviado, o el actual con las nuevas al final; siempre continuo.
        if data.order is not None:
            if sorted(map(str, data.order)) != sorted(map(str, candidates)) or len(data.order) != len(
                candidates
            ):
                raise BusinessRuleError(
                    "El orden debe incluir todas las líneas resultantes, una vez cada una.",
                    code="invalid_order",
                )
            keys: list[int | str] = list(data.order)
        else:
            keys = sorted(candidates, key=lambda k: candidates[k][1])

        after: list[HarvestLine] = []
        refs = {}
        for position, key in enumerate(keys, start=1):
            values, _ = candidates[key]
            ref = self._refs(plan.plant_id, values["cage_id"], values["holding_cage_id"], values["shift_id"])
            refs[key] = ref
            after.append(self._candidate(key, ref, values, position))

        self._block_errors(after, plan, "No se pueden guardar los cambios:")
        if harvest.diff_versions(before, after).is_empty:
            raise BusinessRuleError("No hay cambios para guardar.", code="no_changes")

        # Aplicar.
        for entry_id in deleted:
            plan.entries.remove(entries[entry_id])
        for position, key in enumerate(keys, start=1):
            values, _ = candidates[key]
            farm_center_id = refs[key].cage.farm_center_id
            if isinstance(key, int):
                entry = entries[key]
                for name, value in values.items():
                    if getattr(entry, name) != value:
                        setattr(entry, name, value)
                if entry.farm_center_id != farm_center_id:
                    entry.farm_center_id = farm_center_id
                if entry.sequence != position:
                    entry.sequence = position
            else:
                plan.entries.append(
                    HarvestEntry(
                        plant_id=plan.plant_id, farm_center_id=farm_center_id, sequence=position, **values
                    )
                )
        self._new_version(plan, VersionKind.CHANGE, data.reason)
        self.session.commit()
        return plan

    # Cerrar ------------------------------------------------------------------------------

    def close(self, plan_id: int, row_version: str) -> DailyPlan:
        plan = self.get(plan_id)
        if plan.status == PlanStatus.CLOSED:
            raise BusinessRuleError("El plan ya está cerrado.", code="plan_closed")
        if plan.status == PlanStatus.DRAFT:
            raise BusinessRuleError("Solo se cierra un plan publicado.", code="plan_not_published")
        self._check_version(plan, row_version)
        closable_at = self.closable_at(plan)
        if closable_at is None:
            raise BusinessRuleError(
                "La planta no tiene turnos activos: no se sabe cuándo termina el día.", code="no_shifts"
            )
        if datetime.now(UTC) < closable_at:
            raise BusinessRuleError(
                "La fecha productiva aún no termina: el plan se cierra después del último turno.",
                code="plan_day_not_finished",
                details={"closable_at": closable_at.isoformat()},
            )
        plan.status = PlanStatus.CLOSED
        plan.closed_at = datetime.now(UTC)
        plan.closed_by = self.user.id
        self.session.commit()
        return plan

    # Versiones ---------------------------------------------------------------------------

    def _version(self, plan: DailyPlan, number: int) -> DailyPlanVersion:
        version = repository.get_version(self.session, plan.id, number)
        if version is None:
            raise NotFoundError(f"El plan no tiene versión {number}.", code="version_not_found")
        return version

    @staticmethod
    def _version_out(
        version: DailyPlanVersion, lines: list[HarvestLine], names: dict[int, str], wfe_factor: Decimal | None
    ) -> VersionOut:
        return VersionOut(
            number=version.number,
            kind=version.kind,
            reason=version.reason,
            created_at=version.created_at,
            created_by=version.created_by,
            created_by_name=names.get(version.created_by) if version.created_by else None,
            totals=totals_out(harvest.totals(lines, wfe_factor)),
        )

    def _names(self, versions: list[DailyPlanVersion]) -> dict[int, str]:
        ids = {v.created_by for v in versions if v.created_by}
        if not ids:
            return {}
        rows = self.session.execute(select(User.id, User.full_name).where(User.id.in_(ids)))
        return dict(rows.all())

    def versions(self, plan_id: int) -> list[VersionOut]:
        plan = self.get(plan_id)
        factor = self.rules(plan).wfe_factor
        versions = repository.versions(self.session, plan.id)
        names = self._names(versions)
        return [
            self._version_out(v, repository.version_entries(self.session, v), names, factor)
            for v in reversed(versions)
        ]

    def version_detail(self, plan_id: int, number: int) -> VersionDetailOut:
        plan = self.get(plan_id)
        version = self._version(plan, number)
        lines = repository.version_entries(self.session, version)
        return VersionDetailOut(
            version=self._version_out(version, lines, self._names([version]), self.rules(plan).wfe_factor),
            entries=[line_out(line) for line in lines],
        )

    def compare(self, plan_id: int, a: int, b: int) -> VersionCompareOut:
        plan = self.get(plan_id)
        rules = self.rules(plan)
        before = repository.version_entries(self.session, self._version(plan, a))
        after = repository.version_entries(self.session, self._version(plan, b))
        diff = harvest.diff_versions(before, after, rules.wfe_factor)
        return VersionCompareOut(
            a=a,
            b=b,
            added=[line_out(line) for line in diff.added],
            removed=[line_out(line) for line in diff.removed],
            changed=[
                LineChangeOut(
                    entry_id=int(c.key),
                    label=c.label,
                    changes=[
                        FieldChangeOut(field=f.field, label=f.label, old=_plain(f.old), new=_plain(f.new))
                        for f in c.changes
                    ],
                )
                for c in diff.changed
            ],
            totals_a=totals_out(harvest.totals(before, rules.wfe_factor)),
            totals_b=totals_out(harvest.totals(after, rules.wfe_factor)),
        )
