import hashlib
import socket
import time
import uuid
from datetime import datetime
from pathlib import Path

from app.models.schemas import AnonymizationResult, AnonymizationStats, AnonymizeOptions, AuditInfo, BatchAnonymizationResult
from app.pipeline.anonymizer import ReplacementState, apply_anonymization
from app.pipeline.exporter import export_processing_log, export_text
from app.pipeline.ocr import needs_ocr, run_ocr
from app.pipeline.parser import extract_text
from app.pipeline.regex_rules import detect_entities_by_regex
from app.pipeline.validator import validate_entities, validate_output
from app.services.database import save_job
from app.services.ollama import OllamaDetectionError, detect_entities_with_ollama


def run_pipeline(
    path: Path,
    original_filename: str,
    options: AnonymizeOptions,
    replacement_state: ReplacementState | None = None,
) -> AnonymizationResult:
    started_at = time.perf_counter()
    job_id = str(uuid.uuid4())
    file_bytes = path.read_bytes()
    sha256 = hashlib.sha256(file_bytes).hexdigest().upper()

    original_text = extract_text(path)
    source_layout = _source_pdf_layout(path)
    ocr_used = False
    if needs_ocr(original_text):
        ocr_text = run_ocr(path)
        if ocr_text:
            original_text = ocr_text
            ocr_used = True

    if not options.use_ollama:
        raise ValueError("IA local obrigatoria. Marque ciencia das regras e mantenha o Ollama em execucao.")

    regex_entities = detect_entities_by_regex(original_text, options.document_kind)
    try:
        ollama_entities = detect_entities_with_ollama(original_text, options.model, options.document_kind)
    except OllamaDetectionError as exc:
        raise ValueError(f"IA local obrigatoria indisponivel: {exc}") from exc
    if regex_entities and not ollama_entities:
        raise ValueError(
            "IA local obrigatoria nao retornou entidades para um documento com dados sensiveis detectados por regras. "
            "Verifique se o modelo selecionado esta correto e se o Ollama esta em execucao."
        )
    entities, preserved_dates, preserved_values, warnings = validate_entities(
        original_text,
        regex_entities + ollama_entities,
        options.document_kind,
    )
    anonymized_text, applied, control_rows = apply_anonymization(original_text, entities, replacement_state)
    warnings.extend(validate_output(original_text, anonymized_text, options.document_kind))
    elapsed_for_summary = round(time.perf_counter() - started_at, 3)
    validation_status = "Concluída" if not warnings else "Concluída com avisos"
    export_paths = export_text(
        job_id,
        anonymized_text,
        original_filename,
        {
            "model": options.model,
            "request_title": options.request_title,
            "document_kind": options.document_kind.value,
            "processing_time_seconds": elapsed_for_summary,
            "ocr_used": ocr_used,
            "structure_preserved": options.preserve_layout,
            "validation_status": validation_status,
            "source_sha256": sha256,
            "entities_found": len(entities),
            "replacements_applied": applied,
            "control_table": [row.model_dump() for row in control_rows],
            "source_path": str(path),
            **source_layout,
        },
    )
    export_hashes = {
        format_name: _sha256_file(Path(export_path))
        for format_name, export_path in export_paths.items()
        if Path(export_path).exists()
    }
    elapsed = round(time.perf_counter() - started_at, 3)

    save_job(
        job_id=job_id,
        filename=original_filename,
        document_kind=options.document_kind.value,
        model=options.model,
        entities_found=len(entities),
        replacements_applied=applied,
        sha256=sha256,
    )

    return AnonymizationResult(
        job_id=job_id,
        original_filename=original_filename,
        document_kind=options.document_kind,
        model=options.model,
        original_text=original_text,
        anonymized_text=anonymized_text,
        entities=entities,
        control_table=control_rows,
        stats=AnonymizationStats(
            entities_found=len(entities),
            replacements_applied=applied,
            preserved_dates=preserved_dates,
            preserved_values=preserved_values,
            validation_warnings=warnings,
        ),
        audit=AuditInfo(
            source_sha256=sha256,
            export_sha256=export_hashes,
            processing_time_seconds=elapsed,
            ocr_used=ocr_used,
            structure_preserved=options.preserve_layout,
            validation_status=validation_status,
        ),
        export_paths=export_paths,
    )


def run_batch_pipeline(
    files: list[tuple[Path, str]],
    options: AnonymizeOptions,
    client_host: str | None = None,
) -> BatchAnonymizationResult:
    group_id = str(uuid.uuid4())
    started_at = datetime.now()
    replacement_state = ReplacementState()
    results: list[AnonymizationResult] = []

    for path, original_filename in files:
        results.append(run_pipeline(path, original_filename, options, replacement_state))

    log_path = export_processing_log(
        group_id,
        {
            "summary_lines": [
                f"Numero IP / Nome solicitacao: {options.request_title or 'Nao informado'}",
                f"Data e hora do registro: {started_at.strftime('%d/%m/%Y %H:%M:%S')}",
                f"Modelo local: {options.model}",
                f"Perfil documental: {options.document_kind.value}",
                f"Quantidade de arquivos: {len(results)}",
                f"Host cliente: {client_host or 'Nao identificado'}",
                f"Maquina local: {_local_machine_identity()}",
                "Processamento declarado: local/offline, com hashes SHA-256 para controle de integridade.",
            ],
            "files": [
                {
                    "filename": result.original_filename,
                    "source_sha256": result.audit.source_sha256,
                    "txt_sha256": result.audit.export_sha256.get("txt", ""),
                    "docx_sha256": result.audit.export_sha256.get("docx", ""),
                    "pdf_sha256": result.audit.export_sha256.get("pdf", ""),
                    "csv_sha256": result.audit.export_sha256.get("csv", ""),
                }
                for result in results
            ],
        },
    )
    log_sha256 = _sha256_file(Path(log_path)) if Path(log_path).exists() else None
    return BatchAnonymizationResult(
        group_id=group_id,
        request_title=options.request_title,
        results=results,
        log_sha256=log_sha256,
    )


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _local_machine_identity() -> str:
    hostname = socket.gethostname()
    try:
        address = socket.gethostbyname(hostname)
    except OSError:
        address = "IP local nao identificado"
    return f"{hostname} ({address})"


def _source_pdf_layout(path: Path) -> dict[str, object]:
    if path.suffix.lower() != ".pdf":
        return {}
    try:
        from pypdf import PdfReader

        reader = PdfReader(str(path))
        if not reader.pages:
            return {}
        page = reader.pages[0]
        width = float(page.mediabox.width)
        height = float(page.mediabox.height)
        rotation = int(page.get("/Rotate") or 0)
        visible_landscape = width > height or rotation in {90, 270}
        return {
            "source_pdf_width": width,
            "source_pdf_height": height,
            "source_pdf_rotation": rotation,
            "source_pdf_orientation": "landscape" if visible_landscape else "portrait",
        }
    except Exception:
        return {}
