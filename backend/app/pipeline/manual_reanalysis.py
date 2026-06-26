from __future__ import annotations

import hashlib
import json
import re
import time
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from app.models.schemas import (
    AnonymizationControlRow,
    AnonymizationResult,
    AnonymizationStats,
    AuditInfo,
    DocumentKind,
    Entity,
    EntityType,
    ManualCorrection,
)
from app.pipeline.anonymizer import LABELS, TYPE_LABELS
from app.pipeline.exporter import export_audit_manifest, export_text
from app.services.database import save_job
from app.version import APP_VERSION


@dataclass(frozen=True)
class ManualCorrectionReport:
    requested_value: str
    entity_type: str
    anonymous_id: str
    occurrences: int
    status: str
    note: str


def run_manual_reanalysis(source_job_id: str, corrections: list[ManualCorrection], note: str | None = None) -> AnonymizationResult:
    if not corrections:
        raise ValueError("Informe ao menos uma correcao manual.")

    state_path = Path("data") / "exports" / source_job_id / "estado_reanalise.json"
    if not state_path.exists():
        raise ValueError("Esta solicitacao nao possui estado local para reanalise. Reprocesse o arquivo uma vez e tente novamente.")

    state = json.loads(state_path.read_text(encoding="utf-8"))
    started_at = time.perf_counter()
    job_id = str(uuid.uuid4())
    original_text = str(state.get("original_text") or "")
    original_filename = str(state.get("original_filename") or "documento")
    document_kind = DocumentKind(str(state.get("document_kind") or DocumentKind.relatorio_investigativo.value))
    model = str(state.get("model") or "nexus.op:latest")
    request_title = str(state.get("request_title") or "Reanalise dirigida")
    source_sha256 = str(state.get("source_sha256") or "")
    rows = _rows_from_state(state)
    rows, manual_reports = _merge_manual_corrections(rows, corrections, original_text)
    anonymized_text, replacements_applied, rows, replacement_counts = _apply_rows(original_text, rows)
    manual_reports = _finalize_manual_reports(manual_reports, replacement_counts)

    metadata = dict(state.get("export_metadata") or {})
    metadata.update(
        {
            "model": model,
            "anon_version": APP_VERSION,
            "request_title": request_title,
            "document_kind": document_kind.value,
            "processing_time_seconds": round(time.perf_counter() - started_at, 3),
            "structure_preserved": True,
            "validation_status": "Concluida com reanalise dirigida",
            "source_sha256": source_sha256,
            "entities_found": len(rows),
            "replacements_applied": replacements_applied,
            "control_table": [row.model_dump() for row in rows],
            "validation_warnings": [
                f"Reanalise dirigida pelo operador: {len(corrections)} correcao(oes) manual(is) aplicada(s)."
            ],
            "manual_reanalysis": {
                "source_job_id": source_job_id,
                "created_at": datetime.now().isoformat(timespec="seconds"),
                "note": note or "",
                "corrections": [correction.model_dump() for correction in corrections],
                "report": [report.__dict__ for report in manual_reports],
            },
        }
    )
    source_copy_path = state.get("source_copy_path") or metadata.get("source_copy_path") or metadata.get("source_path")
    if source_copy_path:
        metadata["source_path"] = str(source_copy_path)
        metadata["source_copy_path"] = str(source_copy_path)

    export_paths = export_text(job_id, anonymized_text, original_filename, metadata)
    export_hashes = {
        format_name: _sha256_file(Path(export_path))
        for format_name, export_path in export_paths.items()
        if Path(export_path).exists()
    }
    audit_path = export_audit_manifest(job_id, original_filename, metadata, export_hashes)
    if Path(audit_path).exists():
        export_paths["auditoria"] = audit_path
        export_hashes["auditoria"] = _sha256_file(Path(audit_path))
    reanalysis_log_path = _write_manual_reanalysis_log(
        job_id=job_id,
        source_job_id=source_job_id,
        original_filename=original_filename,
        request_title=request_title,
        document_kind=document_kind.value,
        source_sha256=source_sha256,
        reports=manual_reports,
        export_hashes=export_hashes,
    )
    export_paths["reanalise_log"] = reanalysis_log_path
    export_hashes["reanalise_log"] = _sha256_file(Path(reanalysis_log_path))
    export_hash_reasons = {
        format_name: "Hash atualizado em decorrencia de REANALISE DIRIGIDA."
        for format_name in export_hashes
    }
    reanalysis_timestamp = datetime.now().isoformat(timespec="seconds")
    export_hash_updated_at = {
        format_name: reanalysis_timestamp
        for format_name in export_hashes
    }

    _persist_reanalysis_state(
        job_id,
        {
            **state,
            "schema": "ANON-REANALISE-DIRIGIDA-v1",
            "job_id": job_id,
            "source_job_id": source_job_id,
            "anonymized_text": anonymized_text,
            "control_table": [row.model_dump() for row in rows],
            "export_metadata": metadata,
            "export_sha256": export_hashes,
            "export_sha256_reason": export_hash_reasons,
            "export_sha256_updated_at": export_hash_updated_at,
            "manual_note": note or "",
            "manual_reanalysis_report": [report.__dict__ for report in manual_reports],
            "created_at": reanalysis_timestamp,
        },
    )

    save_job(
        job_id=job_id,
        filename=f"{original_filename} (reanalise dirigida)",
        document_kind=document_kind.value,
        model=model,
        entities_found=len(rows),
        replacements_applied=replacements_applied,
        sha256=source_sha256,
    )

    elapsed = round(time.perf_counter() - started_at, 3)
    entities = _entities_from_rows(original_text, rows)
    return AnonymizationResult(
        job_id=job_id,
        original_filename=original_filename,
        document_kind=document_kind,
        model=model,
        original_text=original_text,
        anonymized_text=anonymized_text,
        entities=entities,
        control_table=rows,
        review_items=[],
        stats=AnonymizationStats(
            entities_found=len(rows),
            replacements_applied=replacements_applied,
            preserved_dates=0,
            preserved_values=0,
            validation_warnings=metadata["validation_warnings"],
            confidence_score=85,
            confidence_level="REANALISE_DIRIGIDA",
            confidence_reasons=["Produto regenerado a partir de correcao manual dirigida pelo operador."],
        ),
        audit=AuditInfo(
            source_sha256=source_sha256,
            export_sha256=export_hashes,
            export_sha256_reason=export_hash_reasons,
            export_sha256_updated_at=export_hash_updated_at,
            processing_time_seconds=elapsed,
            ocr_used=bool(metadata.get("ocr_used")),
            structure_preserved=True,
            validation_status="Concluida com reanalise dirigida",
            anon_version=APP_VERSION,
            safe_summary_id=source_sha256,
            pipeline_state_id=job_id,
        ),
        export_paths=export_paths,
        safe_summary={
            "document_id": source_sha256,
            "profile": document_kind.value,
            "total_entities_detected": len(rows),
            "warnings_raised": metadata["validation_warnings"],
            "confidence_score": 85,
            "confidence_level": "REANALISE_DIRIGIDA",
            "confidence_reasons": ["Correcao manual integrada ao produto regenerado."],
        },
        pipeline_state={
            "pipeline_id": job_id,
            "overall_status": "warn",
            "stages": [
                {"name": "manual_reanalysis", "status": "warn", "note": "Correcao manual dirigida aplicada."},
                {"name": "export", "status": "ok", "note": "Produtos regenerados com novos hashes."},
            ],
        },
    )


def _rows_from_state(state: dict[str, Any]) -> list[AnonymizationControlRow]:
    rows: list[AnonymizationControlRow] = []
    for item in state.get("control_table") or []:
        try:
            rows.append(AnonymizationControlRow.model_validate(item))
        except Exception:
            continue
    return rows


def _merge_manual_corrections(
    rows: list[AnonymizationControlRow],
    corrections: list[ManualCorrection],
    original_text: str,
) -> tuple[list[AnonymizationControlRow], list[ManualCorrectionReport]]:
    output = list(rows)
    existing_by_original = {_normalize(row.original_value): row for row in output}
    reports: list[ManualCorrectionReport] = []
    for correction in corrections:
        value = " ".join(correction.original_value.split())
        if not value:
            continue
        normalized = _normalize(value)
        occurrences = _count_occurrences(original_text, value)
        if normalized in existing_by_original:
            existing = existing_by_original[normalized]
            requested_marker = (correction.anonymous_id or "").strip()
            if requested_marker and requested_marker != existing.anonymous_id:
                updated = AnonymizationControlRow(
                    original_value=existing.original_value,
                    entity_type=existing.entity_type,
                    anonymous_id=requested_marker,
                    occurrences=existing.occurrences,
                )
                output = [updated if _normalize(row.original_value) == normalized else row for row in output]
                existing_by_original[normalized] = updated
                reports.append(
                    ManualCorrectionReport(
                        requested_value=value,
                        entity_type=updated.entity_type,
                        anonymous_id=updated.anonymous_id,
                        occurrences=occurrences,
                        status="aplicado" if occurrences > 0 else "nao_encontrado",
                        note="Marcador existente atualizado por decisao registrada no painel de auditoria."
                        if occurrences > 0
                        else "Marcador atualizado, mas o termo nao foi localizado no texto extraido desta versao.",
                    )
                )
                continue
            reports.append(
                ManualCorrectionReport(
                    requested_value=value,
                    entity_type=existing.entity_type,
                    anonymous_id=existing.anonymous_id,
                    occurrences=occurrences,
                    status="aplicado" if occurrences > 0 else "nao_encontrado",
                    note="Termo ja constava na tabela de anonimização e foi reaplicado no novo produto."
                    if occurrences > 0
                    else "Termo ja existia na tabela, mas nao foi localizado no texto extraido desta versao.",
                )
            )
            continue
        entity_type = correction.entity_type.value
        label = LABELS.get(entity_type, "DADO")
        type_label = TYPE_LABELS.get(entity_type, entity_type)
        anonymous_id = correction.anonymous_id or _next_anonymous_id(output, label)
        if occurrences <= 0:
            reports.append(
                ManualCorrectionReport(
                    requested_value=value,
                    entity_type=type_label,
                    anonymous_id=anonymous_id,
                    occurrences=0,
                    status="nao_encontrado",
                    note="Nenhuma substituicao aplicada. Informe o texto exatamente como consta no documento extraido.",
                )
            )
            continue
        row = AnonymizationControlRow(
            original_value=value,
            entity_type=type_label,
            anonymous_id=anonymous_id,
            occurrences=occurrences,
        )
        output.append(row)
        existing_by_original[normalized] = row
        reports.append(
            ManualCorrectionReport(
                requested_value=value,
                entity_type=type_label,
                anonymous_id=anonymous_id,
                occurrences=occurrences,
                status="aplicado",
                note="Termo encontrado e substituido no novo produto gerado.",
            )
        )
    return output, reports


def _apply_rows(text: str, rows: list[AnonymizationControlRow]) -> tuple[str, int, list[AnonymizationControlRow], dict[str, int]]:
    output = text
    applied_total = 0
    updated_rows: list[AnonymizationControlRow] = []
    replacement_counts: dict[str, int] = {}
    for row in sorted(rows, key=lambda item: len(item.original_value), reverse=True):
        original = row.original_value.strip()
        marker = row.anonymous_id.strip()
        if not original or not marker:
            continue
        output, count = _replace_exact(output, original, marker)
        applied_total += count
        replacement_counts[_normalize(original)] = count
        if count > 0:
            updated_rows.append(
                AnonymizationControlRow(
                    original_value=row.original_value,
                    entity_type=row.entity_type,
                    anonymous_id=row.anonymous_id,
                    occurrences=count,
                )
            )
    return output, applied_total, updated_rows, replacement_counts


def _finalize_manual_reports(
    reports: list[ManualCorrectionReport],
    replacement_counts: dict[str, int],
) -> list[ManualCorrectionReport]:
    finalized: list[ManualCorrectionReport] = []
    for report in reports:
        applied = replacement_counts.get(_normalize(report.requested_value), report.occurrences)
        if applied > 0:
            finalized.append(
                ManualCorrectionReport(
                    requested_value=report.requested_value,
                    entity_type=report.entity_type,
                    anonymous_id=report.anonymous_id,
                    occurrences=applied,
                    status="aplicado",
                    note="Termo substituido com sucesso no novo produto gerado.",
                )
            )
        else:
            finalized.append(
                ManualCorrectionReport(
                    requested_value=report.requested_value,
                    entity_type=report.entity_type,
                    anonymous_id=report.anonymous_id,
                    occurrences=0,
                    status="nao_encontrado",
                    note="Termo nao encontrado. Repetir a reanalise informando o texto exatamente como aparece no documento.",
                )
            )
    return finalized


def _replace_exact(text: str, original: str, marker: str) -> tuple[str, int]:
    pattern = re.compile(rf"(?<![\w\[\]]){re.escape(original)}(?![\w\[\]])", re.IGNORECASE)
    return pattern.subn(marker, text)


def _next_anonymous_id(rows: list[AnonymizationControlRow], label: str) -> str:
    highest = 0
    pattern = re.compile(rf"^\[{re.escape(label)}_(\d{{3,}})\]$")
    for row in rows:
        match = pattern.match(row.anonymous_id.strip())
        if match:
            highest = max(highest, int(match.group(1)))
    return f"[{label}_{highest + 1:03d}]"


def _count_occurrences(text: str, value: str) -> int:
    if not text or not value:
        return 0
    return len(re.findall(rf"(?<![\w\[\]]){re.escape(value)}(?![\w\[\]])", text, flags=re.IGNORECASE))


def _entities_from_rows(text: str, rows: list[AnonymizationControlRow]) -> list[Entity]:
    entities: list[Entity] = []
    for row in rows:
        start = text.lower().find(row.original_value.lower())
        end = start + len(row.original_value) if start >= 0 else 0
        entities.append(
            Entity(
                type=_entity_type_from_label(row.entity_type),
                text=row.original_value,
                start=max(start, 0),
                end=max(end, 0),
                source="manual_reanalysis",
                confidence=1.0,
                reason="Correcao manual dirigida pelo operador.",
                action="anonymize",
            )
        )
    return entities


def _entity_type_from_label(label: str) -> EntityType:
    normalized = _normalize(label)
    for entity_type, type_label in TYPE_LABELS.items():
        if _normalize(type_label) == normalized:
            return EntityType(entity_type)
    return EntityType.other_identifier


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value.casefold()).strip()


def _persist_reanalysis_state(job_id: str, payload: dict[str, Any]) -> None:
    export_dir = Path("data") / "exports" / job_id
    export_dir.mkdir(parents=True, exist_ok=True)
    (export_dir / "estado_reanalise.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_manual_reanalysis_log(
    *,
    job_id: str,
    source_job_id: str,
    original_filename: str,
    request_title: str,
    document_kind: str,
    source_sha256: str,
    reports: list[ManualCorrectionReport],
    export_hashes: dict[str, str],
) -> str:
    export_dir = Path("data") / "exports" / job_id
    export_dir.mkdir(parents=True, exist_ok=True)
    applied = [report for report in reports if report.status == "aplicado"]
    not_found = [report for report in reports if report.status != "aplicado"]
    lines = [
        "ANON - LOG DA REANALISE DIRIGIDA",
        "=" * 72,
        f"Gerado em: {datetime.now().isoformat(timespec='seconds')}",
        f"Solicitacao: {request_title}",
        f"Arquivo original: {original_filename}",
        f"Perfil documental: {document_kind}",
        f"Job original: {source_job_id}",
        f"Novo job: {job_id}",
        f"SHA-256 original: {source_sha256 or 'nao informado'}",
        "",
        "AVISO AO OPERADOR",
        "-" * 72,
        "Para que a reanalise dirigida funcione corretamente, o texto informado deve ser",
        "EXATAMENTE igual ao texto que consta no documento extraido pelo ANON.",
        "Diferencas de acento, espaco, abreviacao, pontuacao, quebra de linha ou caixa podem",
        "impedir a substituicao automatica. Quando um termo nao for encontrado, confira o",
        "produto gerado e repita a reanalise usando a grafia literal exibida no documento.",
        "",
        "RESUMO",
        "-" * 72,
        f"Termos informados: {len(reports)}",
        f"Alteracoes aplicadas com sucesso: {len(applied)}",
        f"Termos nao encontrados: {len(not_found)}",
        f"Total de ocorrencias substituidas: {sum(report.occurrences for report in applied)}",
        "",
        "DETALHAMENTO DAS ALTERACOES",
        "-" * 72,
    ]
    for index, report in enumerate(reports, start=1):
        status = "APLICADO COM SUCESSO" if report.status == "aplicado" else "NAO ENCONTRADO"
        lines.extend(
            [
                f"{index}. Status: {status}",
                f"   Valor informado: {report.requested_value}",
                f"   Tipo: {report.entity_type}",
                f"   Novo termo substituido: {report.anonymous_id}",
                f"   Ocorrencias substituidas: {report.occurrences}",
                f"   Observacao: {report.note}",
                "",
            ]
        )
    lines.extend(
        [
            "HASHES DOS PRODUTOS GERADOS",
            "-" * 72,
        ]
    )
    for format_name, digest in sorted(export_hashes.items()):
        lines.append(f"{format_name.upper()}: {digest}")
    lines.extend(
        [
            "",
            "CONSIDERACOES FINAIS",
            "-" * 72,
            "Este log registra exclusivamente a reanalise dirigida realizada pelo operador.",
            "Ele deve ser mantido junto ao produto reprocessado para conferencia interna,",
            "rastreabilidade e revisao humana obrigatoria antes de qualquer uso institucional.",
            "",
        ]
    )
    log_path = export_dir / "log_reanalise_dirigida.txt"
    log_path.write_text("\n".join(lines), encoding="utf-8")
    return str(log_path)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()
