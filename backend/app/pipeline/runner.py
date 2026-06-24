import hashlib
import time
import uuid
from pathlib import Path

from app.models.schemas import AnonymizationResult, AnonymizationStats, AnonymizeOptions, AuditInfo
from app.pipeline.anonymizer import apply_anonymization
from app.pipeline.exporter import export_text
from app.pipeline.ocr import needs_ocr, run_ocr
from app.pipeline.parser import extract_text
from app.pipeline.regex_rules import detect_entities_by_regex
from app.pipeline.validator import validate_entities, validate_output
from app.services.database import save_job
from app.services.ollama import detect_entities_with_ollama


def run_pipeline(path: Path, original_filename: str, options: AnonymizeOptions) -> AnonymizationResult:
    started_at = time.perf_counter()
    job_id = str(uuid.uuid4())
    file_bytes = path.read_bytes()
    sha256 = hashlib.sha256(file_bytes).hexdigest().upper()

    original_text = extract_text(path)
    ocr_used = False
    if needs_ocr(original_text):
        ocr_text = run_ocr(path)
        if ocr_text:
            original_text = ocr_text
            ocr_used = True

    regex_entities = detect_entities_by_regex(original_text, options.document_kind)
    ollama_entities = (
        detect_entities_with_ollama(original_text, options.model, options.document_kind)
        if options.use_ollama
        else []
    )
    entities, preserved_dates, preserved_values, warnings = validate_entities(
        original_text,
        regex_entities + ollama_entities,
        options.document_kind,
    )
    anonymized_text, applied = apply_anonymization(original_text, entities)
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


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()
