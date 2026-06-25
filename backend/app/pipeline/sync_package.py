from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from app.models.schemas import AnonymizationControlRow, AnonymizationSyncEntry, Entity, EntityType
from app.pipeline.anonymizer import LABELS, TYPE_LABELS, ReplacementState


SYNC_SCHEMA = "ANON-SYNC-PACKAGE-v1"


def build_sync_package_from_state(job_id: str) -> dict[str, Any]:
    state_path = Path("data") / "exports" / job_id / "estado_reanalise.json"
    if not state_path.exists():
        raise ValueError("Estado de anonimização não encontrado para gerar pacote de sincronização.")
    state = json.loads(state_path.read_text(encoding="utf-8"))
    if state.get("document_kind") == "personalizado":
        raise ValueError("O perfil Personalizado nao permite pacote de sincronizacao.")
    rows = []
    for item in state.get("control_table") or []:
        try:
            row = AnonymizationControlRow.model_validate(item)
        except Exception:
            continue
        entity_type = _entity_type_from_label(row.entity_type)
        if not row.original_value.strip() or not row.anonymous_id.strip():
            continue
        rows.append(
            {
                "original_value": row.original_value,
                "entity_type": entity_type.value,
                "entity_label": row.entity_type,
                "anonymous_id": row.anonymous_id,
                "occurrences": row.occurrences,
            }
        )
    return {
        "schema": SYNC_SCHEMA,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "source_job_id": job_id,
        "request_title": state.get("request_title") or state.get("export_metadata", {}).get("request_title"),
        "original_filename": state.get("original_filename"),
        "document_kind": state.get("document_kind"),
        "source_sha256": state.get("source_sha256"),
        "entries": rows,
        "operator_notice": (
            "Pacote interno para sincronizar anonimizações em outra demanda. "
            "Use apenas quando desejar manter exatamente os mesmos marcadores para os mesmos termos."
        ),
    }


def write_sync_package(job_id: str) -> Path:
    package = build_sync_package_from_state(job_id)
    export_dir = Path("data") / "exports" / job_id
    export_dir.mkdir(parents=True, exist_ok=True)
    path = export_dir / "pacote_sincronizacao_anon.json"
    path.write_text(json.dumps(package, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def parse_sync_package(content: bytes, filename: str | None = None) -> list[AnonymizationSyncEntry]:
    if filename and not filename.lower().endswith(".json"):
        raise ValueError("A sincronizacao de anonimizacao aceita somente pacote JSON gerado pelo ANON.")
    text = content.decode("utf-8-sig", errors="replace")
    payload = json.loads(text)
    entries = payload.get("entries") or payload.get("control_table") or []
    output: list[AnonymizationSyncEntry] = []
    for item in entries:
        original = str(item.get("original_value") or "").strip()
        anonymous_id = str(item.get("anonymous_id") or "").strip()
        if not original or not anonymous_id:
            continue
        entity_type = _entity_type_from_any(item.get("entity_type") or item.get("entity_label"))
        output.append(
            AnonymizationSyncEntry(
                original_value=original,
                entity_type=entity_type,
                anonymous_id=anonymous_id,
                source="sync_package",
            )
        )
    return _dedupe_entries(output)


def apply_sync_entries_to_state(state: ReplacementState, entries: list[AnonymizationSyncEntry]) -> int:
    from app.core.nce import canonical_entity_key

    applied = 0
    for entry in entries:
        original = entry.original_value.strip()
        marker = entry.anonymous_id.strip()
        if not original or not marker:
            continue
        key = canonical_entity_key(entry.entity_type.value, original)
        state.replacements[key] = marker
        _update_counter_from_marker(state, marker)
        applied += 1
    return applied


def detect_sync_entities(text: str, entries: list[AnonymizationSyncEntry]) -> list[Entity]:
    entities: list[Entity] = []
    for entry in entries:
        original = entry.original_value.strip()
        if not original:
            continue
        pattern = re.compile(rf"(?<![\w\[\]]){re.escape(original)}(?![\w\[\]])", re.IGNORECASE)
        for match in pattern.finditer(text):
            entities.append(
                Entity(
                    type=entry.entity_type,
                    text=match.group(0),
                    start=match.start(),
                    end=match.end(),
                    source="sync_package",
                    confidence=1.0,
                    reason="Sincronização de anonimização importada pelo operador.",
                    action="anonymize",
                )
            )
    return entities


def _parse_reanalysis_log_text(text: str) -> list[AnonymizationSyncEntry]:
    blocks = re.split(r"\n(?=\d+\.\s+Status:)", text)
    entries: list[AnonymizationSyncEntry] = []
    for block in blocks:
        if "Status: APLICADO COM SUCESSO" not in block:
            continue
        original = _extract_log_field(block, "Valor informado")
        entity_label = _extract_log_field(block, "Tipo")
        anonymous_id = _extract_log_field(block, "Novo termo substituido")
        if original and anonymous_id:
            entries.append(
                AnonymizationSyncEntry(
                    original_value=original,
                    entity_type=_entity_type_from_any(entity_label),
                    anonymous_id=anonymous_id,
                    source="reanalysis_log",
                )
            )
    return _dedupe_entries(entries)


def _extract_log_field(block: str, label: str) -> str:
    match = re.search(rf"^\s*{re.escape(label)}:\s*(.+?)\s*$", block, re.MULTILINE)
    return match.group(1).strip() if match else ""


def _dedupe_entries(entries: list[AnonymizationSyncEntry]) -> list[AnonymizationSyncEntry]:
    seen: set[tuple[str, str]] = set()
    output: list[AnonymizationSyncEntry] = []
    for entry in entries:
        key = (entry.entity_type.value, re.sub(r"\s+", " ", entry.original_value.casefold()).strip())
        if key in seen:
            continue
        seen.add(key)
        output.append(entry)
    return output


def _entity_type_from_any(value: object) -> EntityType:
    text = str(value or "").strip()
    if not text:
        return EntityType.other_identifier
    try:
        return EntityType(text)
    except ValueError:
        return _entity_type_from_label(text)


def _entity_type_from_label(label: str) -> EntityType:
    normalized = _normalize(label)
    for entity_type, type_label in TYPE_LABELS.items():
        if _normalize(type_label) == normalized:
            return EntityType(entity_type)
    for entity_type, marker_label in LABELS.items():
        if _normalize(marker_label) == normalized:
            return EntityType(entity_type)
    return EntityType.other_identifier


def _update_counter_from_marker(state: ReplacementState, marker: str) -> None:
    match = re.match(r"^\[([A-Z0-9_]+)_(\d+)\]$", marker.strip(), re.I)
    if not match:
        return
    label = match.group(1).upper()
    number = int(match.group(2))
    state.counters[label] = max(state.counters.get(label, 0), number)


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value.casefold()).strip()
