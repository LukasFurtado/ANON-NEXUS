import hashlib
import socket
import time
import uuid
from datetime import datetime
from pathlib import Path

from app.core.pipeline_state import PipelineStateEmitter
from app.core.profile_loader import load_profile
from app.core.quality_classifier import classify_quality
from app.core.safe_summary import generate_safe_summary, persist_safe_summary
from app.models.schemas import AnonymizationResult, AnonymizationStats, AnonymizeOptions, AuditInfo, BatchAnonymizationResult
from app.pipeline.anonymizer import ReplacementState, apply_anonymization
from app.pipeline.exporter import export_processing_log, export_text
from app.pipeline.ocr import needs_ocr, run_ocr
from app.pipeline.parser import extract_text
from app.pipeline.regex_rules import detect_entities_by_regex
from app.pipeline.validator import validate_entities, validate_output
from app.services.database import save_job
from app.services.data_protection import build_protection_marker, protection_metadata
from app.services.communication_bus import CommunicationTrace
from app.services.ollama import OllamaDetectionError, detect_entities_with_ollama
from app.version import APP_VERSION


def run_pipeline(
    path: Path,
    original_filename: str,
    options: AnonymizeOptions,
    replacement_state: ReplacementState | None = None,
) -> AnonymizationResult:
    started_at = time.perf_counter()
    job_id = str(uuid.uuid4())
    state = PipelineStateEmitter(job_id)
    active_profile = load_profile(options.document_kind.value)
    trace = CommunicationTrace()
    trace.emit(
        "ANON",
        "arquivo_recebido",
        "Arquivo recebido pelo pipeline local.",
        filename=original_filename,
        profile=options.document_kind.value,
        model=options.model,
    )
    file_bytes = path.read_bytes()
    sha256 = hashlib.sha256(file_bytes).hexdigest().upper()
    trace.emit("ANON", "hash_origem", "Hash SHA-256 do arquivo original calculado.", sha256=sha256)

    state.stage_start("parser", path.suffix.lower())
    original_text = extract_text(path)
    state.stage_ok("parser", f"{len(original_text)} caracteres extraidos")
    trace.emit(
        "Parser",
        "extracao_textual",
        "Texto extraido do arquivo para analise local.",
        characters=len(original_text),
        extension=path.suffix.lower(),
    )
    source_layout = _source_pdf_layout(path)
    if source_layout:
        trace.emit(
            "Parser",
            "layout_origem",
            "Caracteristicas basicas do PDF original foram capturadas.",
            orientation=source_layout.get("source_pdf_orientation"),
            rotation=source_layout.get("source_pdf_rotation"),
        )
    ocr_used = False
    if needs_ocr(original_text):
        trace.emit("OCR", "ocr_necessario", "Texto extraido insuficiente; OCR local sera tentado.", level="warning")
        ocr_text = run_ocr(path)
        if ocr_text:
            original_text = ocr_text
            ocr_used = True
            trace.emit("OCR", "ocr_concluido", "OCR local retornou texto aproveitavel.", characters=len(original_text))
        else:
            trace.emit("OCR", "ocr_sem_retorno", "OCR local nao retornou texto aproveitavel.", level="warning")
    else:
        trace.emit("OCR", "ocr_dispensado", "OCR nao foi necessario para este arquivo.")

    if not options.use_ollama:
        trace.emit("Politica", "ia_obrigatoria", "Processamento bloqueado porque a ciencia de uso da IA local nao foi confirmada.", level="error")
        raise ValueError("IA local obrigatoria. Marque ciencia das regras e mantenha o Ollama em execucao.")

    state.stage_start("regex", "regras locais")
    regex_entities = detect_entities_by_regex(original_text, options.document_kind)
    state.stage_ok("regex", f"{len(regex_entities)} candidatos")
    trace.emit("Regex", "entidades_regex", "Regras locais identificaram entidades candidatas.", count=len(regex_entities))
    warnings: list[str] = []
    ollama_metrics = {
        "chunks_processed": 0,
        "json_rejected_chunks": 0,
        "correction_attempts": 0,
        "correction_successes": 0,
    }
    try:
        state.stage_start("ner", "ia local")
        trace.emit("IA local", "ollama_enviado", "Texto foi enviado ao modelo local para deteccao semantica de entidades.", model=options.model)
        ollama_result = detect_entities_with_ollama(original_text, options.model, options.document_kind)
        ollama_entities = ollama_result.entities
        ollama_metrics = {
            "chunks_processed": ollama_result.chunks_processed,
            "json_rejected_chunks": ollama_result.json_rejected_chunks,
            "correction_attempts": ollama_result.correction_attempts,
            "correction_successes": ollama_result.correction_successes,
        }
        trace.emit(
            "IA local",
            "ollama_resposta",
            "Modelo local retornou resposta avaliada pelo ANON.",
            entities=len(ollama_entities),
            **ollama_metrics,
            level="warning" if ollama_result.json_rejected_chunks else "info",
        )
        state.stage_ok("ner", f"{len(ollama_entities)} entidades")
    except OllamaDetectionError as exc:
        state.stage_fail("ner", "ia local indisponivel")
        trace.emit("IA local", "ollama_indisponivel", "IA local obrigatoria nao retornou resposta utilizavel.", level="error")
        raise ValueError(f"IA local obrigatoria indisponivel: {exc}") from exc
    if not ollama_entities:
        warnings.append(
            "IA local executada, mas nao retornou entidades aproveitaveis em JSON. As regras locais de apoio foram usadas para manter a anonimizacao auditavel; revise o produto final."
        )
        trace.emit("Validador", "ia_sem_entidades", "IA local executada sem entidades aproveitaveis; regras locais sustentaram o processamento.", level="warning")
    state.stage_start("validation", "validacao de entidades")
    entities, preserved_dates, preserved_values, validation_warnings = validate_entities(
        original_text,
        regex_entities + ollama_entities,
        options.document_kind,
    )
    if validation_warnings:
        state.stage_warn("validation", f"{len(validation_warnings)} avisos")
    else:
        state.stage_ok("validation", "sem avisos")
    warnings.extend(validation_warnings)
    trace.emit(
        "Validador",
        "entidades_validadas",
        "Entidades candidatas foram filtradas conforme perfil documental e regras de preservacao.",
        valid_entities=len(entities),
        preserved_dates=preserved_dates,
        preserved_values=preserved_values,
        validation_warnings=len(validation_warnings),
        level="warning" if validation_warnings else "info",
    )
    state.stage_start("substitution", "aplicacao de substituicoes")
    anonymized_text, applied, control_rows = apply_anonymization(original_text, entities, replacement_state)
    state.stage_ok("substitution", f"{applied} substituicoes")
    trace.emit(
        "Anonimizador",
        "substituicoes_aplicadas",
        "Substituicoes foram aplicadas pelo backend do ANON.",
        replacements=applied,
        control_rows=len(control_rows),
    )
    warnings.extend(validate_output(original_text, anonymized_text, options.document_kind))
    trace.emit(
        "Validador",
        "validacao_saida",
        "Saida anonimizada foi comparada com regras de preservacao do perfil.",
        total_warnings=len(warnings),
        level="warning" if warnings else "info",
    )
    elapsed_for_summary = round(time.perf_counter() - started_at, 3)
    validation_status = "Concluída" if not warnings else "Concluída com avisos"
    protection = protection_metadata(
        build_protection_marker(
            source_sha256=sha256,
            request_title=options.request_title,
            original_filename=original_filename,
        )
    )
    state.stage_start("export", "geracao de produtos")
    export_paths = export_text(
        job_id,
        anonymized_text,
        original_filename,
        {
            "model": options.model,
            "anon_version": APP_VERSION,
            "request_title": options.request_title,
            "document_kind": options.document_kind.value,
            "processing_time_seconds": elapsed_for_summary,
            "ocr_used": ocr_used,
            "structure_preserved": options.preserve_layout,
            "validation_status": validation_status,
            "source_sha256": sha256,
            "entities_found": len(entities),
            "replacements_applied": applied,
            "validation_warnings": warnings,
            "ollama_metrics": ollama_metrics,
            "communication_events": trace.public_events(),
            "communication_summary": trace.summary(),
            "control_table": [row.model_dump() for row in control_rows],
            "source_path": str(path),
            "data_protection": protection,
            **source_layout,
        },
    )
    export_hashes = {
        format_name: _sha256_file(Path(export_path))
        for format_name, export_path in export_paths.items()
        if Path(export_path).exists()
    }
    state.stage_ok("export", f"{len(export_hashes)} produto(s)")
    trace.emit(
        "Exportador",
        "produtos_gerados",
        "Produtos exportaveis foram gerados e tiveram hash calculado.",
        formats=list(export_hashes.keys()),
        exports=len(export_hashes),
    )
    elapsed = round(time.perf_counter() - started_at, 3)
    trace.emit("ANON", "processamento_concluido", "Pipeline local concluido.", elapsed_seconds=elapsed)
    pipeline_state = state.finalize()
    pipeline_payload = {
        "original_text": original_text,
        "document_kind": options.document_kind.value,
        "entities": [entity.model_dump() for entity in entities],
        "stats": {
            "entities_found": len(entities),
            "replacements_applied": applied,
            "validation_warnings": warnings,
        },
        "audit": {
            "source_sha256": sha256,
            "export_sha256": export_hashes,
            "processing_time_seconds": elapsed,
        },
        "profile_preserve_always": active_profile.get("preserve_always", []),
        "pipeline_stages_ok": [
            stage["name"]
            for stage in pipeline_state.get("stages", [])
            if stage.get("status") in {"ok", "warn"}
        ],
    }
    safe_summary = generate_safe_summary(pipeline_payload)
    quality = classify_quality(safe_summary, active_profile)
    safe_summary["quality_status"] = quality.status
    safe_summary["quality_score"] = quality.score
    safe_summary["quality_reasons"] = quality.reasons
    persist_safe_summary(safe_summary)

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
            ollama_chunks_processed=ollama_metrics["chunks_processed"],
            ollama_json_rejected_chunks=ollama_metrics["json_rejected_chunks"],
            ollama_correction_attempts=ollama_metrics["correction_attempts"],
            ollama_correction_successes=ollama_metrics["correction_successes"],
            communication_events=trace.public_events(),
            communication_summary=trace.summary(),
            quality_status=quality.status,
            quality_score=quality.score,
            quality_reasons=quality.reasons,
        ),
        audit=AuditInfo(
            source_sha256=sha256,
            export_sha256=export_hashes,
            processing_time_seconds=elapsed,
            ocr_used=ocr_used,
            structure_preserved=options.preserve_layout,
            validation_status=validation_status,
            anon_version=APP_VERSION,
            safe_summary_id=sha256,
            pipeline_state_id=job_id,
        ),
        export_paths=export_paths,
        safe_summary=safe_summary,
        pipeline_state=pipeline_state,
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
                f"Versao do ANON: {APP_VERSION}",
                f"Perfil documental: {options.document_kind.value}",
                f"Quantidade de arquivos: {len(results)}",
                f"Host cliente: {client_host or 'Nao identificado'}",
                f"Maquina local: {_local_machine_identity()}",
                "Protecao de dados: ativa",
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
                    "avisos_sha256": result.audit.export_sha256.get("avisos", ""),
                    "communication_events": result.stats.communication_summary.get("events", 0),
                    "communication_last_stage": result.stats.communication_summary.get("last_stage", ""),
                    "anon_version": result.audit.anon_version or APP_VERSION,
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
