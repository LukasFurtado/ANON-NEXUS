import hashlib
import socket
import time
import uuid
from datetime import datetime
from pathlib import Path

from app.core.confidence import compute_confidence
from app.core.human_review import build_review_items
from app.core.pipeline_state import PipelineStateEmitter
from app.core.nce import NCEGroupContext
from app.core.profile_loader import load_profile
from app.core.quality_classifier import classify_quality
from app.core.safe_summary import generate_safe_summary, persist_safe_summary
from app.models.schemas import AnonymizationResult, AnonymizationStats, AnonymizeOptions, AuditInfo, BatchAnonymizationResult
from app.pipeline.anonymizer import ReplacementState, apply_anonymization
from app.pipeline.exporter import export_audit_manifest, export_processing_log, export_text
from app.pipeline.ocr import needs_ocr, run_ocr
from app.pipeline.parser import extract_text, inspect_source_document
from app.pipeline.post_validator import validate_post_anonymization
from app.pipeline.regex_rules import detect_entities_by_regex
from app.pipeline.sync_package import apply_sync_entries_to_state, detect_sync_entities
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
    nce_context: NCEGroupContext | None = None,
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
    source_copy_path = _persist_source_copy(job_id, path, original_filename)
    trace.emit("ANON", "hash_origem", "Hash SHA-256 do arquivo original calculado.", sha256=sha256)

    state.stage_start("parser", path.suffix.lower())
    original_text = extract_text(path)
    parser_metadata = inspect_source_document(path, original_text)
    state.stage_ok("parser", f"{len(original_text)} caracteres extraidos")
    if nce_context is None:
        nce_context = NCEGroupContext.start(
            request_title=options.request_title,
            document_kind=options.document_kind,
            model=options.model,
            replacement_state=replacement_state,
        )
    if options.sync_entries:
        loaded_sync_entries = apply_sync_entries_to_state(nce_context.replacement_state, options.sync_entries)
        trace.emit(
            "NCE",
            "sincronizacao_importada",
            "Pacote de sincronizacao carregado para manter marcadores ja utilizados em outra demanda.",
            entries=loaded_sync_entries,
        )
    nce_file_context = nce_context.prepare_file(
        filename=original_filename,
        text=original_text,
        source_sha256=sha256,
        extension=path.suffix.lower(),
    )
    trace.emit(
        "NCE",
        "contexto_documental",
        "NCE classificou o arquivo e vinculou ao dicionario de consistencia do grupo.",
        group_id=nce_context.group_id,
        subtype=nce_file_context.subtype,
        role=nce_file_context.role_label,
        expected_sensitive_domains=nce_file_context.expected_sensitive_domains,
        dictionary_size=len(nce_context.replacement_state.replacements),
    )
    nce_context.coordinate(
        nce_file_context,
        stage="parser",
        summary="Texto extraido recebido pelo NCE para coordenacao das etapas seguintes.",
        **parser_metadata,
    )
    trace.emit(
        "Parser",
        "extracao_textual",
        "Texto extraido do arquivo para analise local.",
        **parser_metadata,
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
    nce_context.coordinate(nce_file_context, stage="ocr", summary="NCE avaliou necessidade de OCR local.")
    if needs_ocr(original_text):
        trace.emit("OCR", "ocr_necessario", "Texto extraido insuficiente; OCR local sera tentado.", level="warning")
        ocr_text = run_ocr(path)
        if ocr_text:
            original_text = ocr_text
            ocr_used = True
            nce_context.coordinate(
                nce_file_context,
                stage="ocr",
                status="completed",
                summary="OCR local retornou texto aproveitavel para continuidade.",
                characters=len(original_text),
            )
            trace.emit("OCR", "ocr_concluido", "OCR local retornou texto aproveitavel.", characters=len(original_text))
        else:
            nce_context.coordinate(
                nce_file_context,
                stage="ocr",
                status="warning",
                summary="OCR local nao retornou texto aproveitavel.",
            )
            trace.emit("OCR", "ocr_sem_retorno", "OCR local nao retornou texto aproveitavel.", level="warning")
    else:
        nce_context.coordinate(nce_file_context, stage="ocr", status="skipped", summary="OCR dispensado pelo texto extraido.")
        trace.emit("OCR", "ocr_dispensado", "OCR nao foi necessario para este arquivo.")

    if not options.use_ollama:
        trace.emit("Politica", "ia_obrigatoria", "Processamento bloqueado porque a ciencia de uso da IA local nao foi confirmada.", level="error")
        raise ValueError("IA local obrigatoria. Marque ciencia das regras e mantenha o Ollama em execucao.")

    state.stage_start("regex", "regras locais")
    nce_context.coordinate(
        nce_file_context,
        stage="regex",
        summary="NCE encaminhou texto para regras deterministicas do perfil documental.",
        expected_sensitive_domains=nce_file_context.expected_sensitive_domains,
    )
    regex_entities = detect_entities_by_regex(original_text, options.document_kind, original_filename)
    sync_entities = detect_sync_entities(original_text, options.sync_entries) if options.sync_entries else []
    if sync_entities:
        trace.emit(
            "NCE",
            "entidades_sincronizadas",
            "Termos do pacote de sincronizacao foram localizados no novo documento.",
            count=len(sync_entities),
        )
    nce_context.coordinate(
        nce_file_context,
        stage="regex",
        status="completed",
        summary="Regras locais retornaram candidatos para avaliacao.",
        candidates=len(regex_entities),
        sync_candidates=len(sync_entities),
    )
    state.stage_ok("regex", f"{len(regex_entities)} candidatos")
    trace.emit("Regex", "entidades_regex", "Regras locais identificaram entidades candidatas.", count=len(regex_entities))
    warnings: list[str] = []
    ollama_metrics = {
        "chunks_processed": 0,
        "json_rejected_chunks": 0,
        "correction_attempts": 0,
        "correction_successes": 0,
        "json_rejection_reasons": [],
        "failure_reason": None,
        "preserved_items": 0,
    }
    ollama_entities = []
    try:
        state.stage_start("ner", "ia local")
        nce_context.coordinate(
            nce_file_context,
            stage="ia_local",
            summary="NCE encaminhou o documento para avaliacao semantica da IA local.",
            model=options.model,
        )
        trace.emit("IA local", "ollama_enviado", "Texto foi enviado ao modelo local para deteccao semantica de entidades.", model=options.model)
        ollama_result = detect_entities_with_ollama(original_text, options.model, options.document_kind)
        ollama_entities = ollama_result.entities
        ollama_metrics = {
            "chunks_processed": ollama_result.chunks_processed,
            "json_rejected_chunks": ollama_result.json_rejected_chunks,
            "correction_attempts": ollama_result.correction_attempts,
            "correction_successes": ollama_result.correction_successes,
            "json_rejection_reasons": ollama_result.json_rejection_reasons or [],
            "failure_reason": None,
            "preserved_items": ollama_result.preserved_items,
        }
        trace.emit(
            "IA local",
            "ollama_resposta",
            "Modelo local retornou resposta avaliada pelo ANON.",
            entities=len(ollama_entities),
            **ollama_metrics,
            level="warning" if ollama_result.json_rejected_chunks else "info",
        )
        nce_context.coordinate(
            nce_file_context,
            stage="ia_local",
            status="warning" if ollama_result.json_rejected_chunks else "completed",
            summary="Resposta da IA local foi registrada pelo NCE.",
            entities=len(ollama_entities),
            json_rejected_chunks=ollama_result.json_rejected_chunks,
            correction_attempts=ollama_result.correction_attempts,
        )
        state.stage_ok("ner", f"{len(ollama_entities)} entidades")
    except OllamaDetectionError as exc:
        failure_reason = _safe_ollama_failure_reason(exc)
        ollama_metrics["failure_reason"] = failure_reason
        ollama_metrics["json_rejection_reasons"] = [failure_reason]
        warnings.append(
            "IA local foi acionada, mas nao retornou resposta aproveitavel nesta execucao. "
            "O ANON concluiu o processamento com regras locais de apoio e exige revisao humana do produto final."
        )
        state.stage_warn("ner", "ia local sem resposta aproveitavel")
        nce_context.coordinate(
            nce_file_context,
            stage="ia_local",
            status="warning",
            decision="fallback_local",
            summary="IA local nao retornou resposta aproveitavel; NCE autorizou fallback local auditavel.",
            reason=failure_reason,
        )
        trace.emit(
            "NCE",
            "fallback_local_autorizado",
            "NCE autorizou continuidade com regras locais de apoio apos falha da IA local.",
            level="warning",
            reason=failure_reason,
        )
        trace.emit(
            "IA local",
            "ollama_fallback_local",
            "IA local foi acionada, mas o processamento seguiu com regras locais auditaveis.",
            level="warning",
            reason=failure_reason,
        )
    if not ollama_entities:
        warnings.append(
            "IA local executada, mas nao retornou entidades aproveitaveis em JSON. As regras locais de apoio foram usadas para manter a anonimizacao auditavel; revise o produto final."
        )
        trace.emit("Validador", "ia_sem_entidades", "IA local executada sem entidades aproveitaveis; regras locais sustentaram o processamento.", level="warning")
    state.stage_start("validation", "validacao de entidades")
    nce_context.coordinate(
        nce_file_context,
        stage="validation",
        summary="NCE reuniu candidatos locais e semanticos para validacao por perfil.",
        regex_candidates=len(regex_entities),
        ia_candidates=len(ollama_entities),
        sync_candidates=len(sync_entities),
    )
    entities, preserved_dates, preserved_values, validation_warnings = validate_entities(
        original_text,
        sync_entities + regex_entities + ollama_entities,
        options.document_kind,
    )
    if validation_warnings:
        state.stage_warn("validation", f"{len(validation_warnings)} avisos")
    else:
        state.stage_ok("validation", "sem avisos")
    warnings.extend(validation_warnings)
    nce_context.coordinate(
        nce_file_context,
        stage="validation",
        status="warning" if validation_warnings else "completed",
        summary="Validador retornou entidades aprovadas e preservacoes.",
        valid_entities=len(entities),
        preserved_dates=preserved_dates,
        preserved_values=preserved_values,
        warnings=len(validation_warnings),
    )
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
    nce_context.coordinate(
        nce_file_context,
        stage="substitution",
        summary="NCE forneceu dicionario compartilhado para consistencia de substituicoes.",
        dictionary_size=len(nce_context.replacement_state.replacements),
    )
    active_replacement_state = nce_context.replacement_state
    anonymized_text, applied, control_rows = apply_anonymization(original_text, entities, active_replacement_state)
    nce_context.coordinate(
        nce_file_context,
        stage="substitution",
        status="completed",
        summary="Substituicoes aplicadas e dicionario de consistencia atualizado.",
        replacements=applied,
        control_rows=len(control_rows),
        dictionary_size=len(nce_context.replacement_state.replacements),
    )
    state.stage_ok("substitution", f"{applied} substituicoes")
    trace.emit(
        "Anonimizador",
        "substituicoes_aplicadas",
        "Substituicoes foram aplicadas pelo backend do ANON.",
        replacements=applied,
        control_rows=len(control_rows),
    )
    warnings.extend(validate_output(original_text, anonymized_text, options.document_kind))
    post_validation = validate_post_anonymization(original_text, anonymized_text, options.document_kind, original_filename)
    warnings.extend(post_validation.warnings)
    confidence = compute_confidence(
        replacements_applied=applied,
        validation_warnings=warnings,
        post_validation=post_validation.as_dict(),
        ollama_metrics=ollama_metrics,
        structure_preserved=options.preserve_layout,
        ocr_used=ocr_used,
    )
    review_items = build_review_items(
        control_rows=control_rows,
        validation_warnings=warnings,
        post_validation=post_validation.as_dict(),
        confidence=confidence.as_dict(),
    )
    nce_context.coordinate(
        nce_file_context,
        stage="output_validation",
        status="warning" if warnings else "completed",
        summary="NCE registrou validacao de saida anonimizada.",
        warnings=len(warnings),
        post_validation_score=post_validation.score,
        residual_entities=post_validation.residual_entities,
        anonymous_markers=post_validation.anonymous_markers,
        structure_warnings=post_validation.structure_warnings,
        confidence_score=confidence.score,
        review_items=len(review_items),
    )
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
    nce_context.coordinate(
        nce_file_context,
        stage="export",
        summary="NCE autorizou geracao de produtos exportaveis e internos.",
        validation_status=validation_status,
    )
    export_metadata = {
        "model": options.model,
        "anon_version": APP_VERSION,
        "request_title": options.request_title,
        "document_kind": options.document_kind.value,
        "processing_time_seconds": elapsed_for_summary,
        "ocr_used": ocr_used,
        "structure_preserved": options.preserve_layout,
        "validation_status": validation_status,
        "source_sha256": sha256,
        "parser_metadata": parser_metadata,
        "entities_found": len(entities),
        "replacements_applied": applied,
        "sync_entries_loaded": len(options.sync_entries),
        "sync_entities_found": len(sync_entities),
        "validation_warnings": warnings,
        "ollama_metrics": ollama_metrics,
        "post_validation": post_validation.as_dict(),
        "confidence": confidence.as_dict(),
        "review_items": review_items,
        "communication_events": trace.public_events(),
        "communication_summary": trace.summary(),
        "nce_context": nce_context.public_metadata(),
        "nce_file_context": {
            "subtype": nce_file_context.subtype,
            "role_label": nce_file_context.role_label,
            "expected_sensitive_domains": nce_file_context.expected_sensitive_domains,
            "coordination_log": [
                {
                    "stage": item.stage,
                    "status": item.status,
                    "decision": item.decision,
                    "summary": item.summary,
                    "data": item.data,
                    "created_at": item.created_at,
                }
                for item in nce_file_context.coordination_log
            ],
        },
        "control_table": [row.model_dump() for row in control_rows],
        "source_path": str(source_copy_path),
        "source_copy_path": str(source_copy_path),
        "data_protection": protection,
        **source_layout,
    }
    export_paths = export_text(
        job_id,
        anonymized_text,
        original_filename,
        export_metadata,
    )
    export_hashes = {
        format_name: _sha256_file(Path(export_path))
        for format_name, export_path in export_paths.items()
        if Path(export_path).exists()
    }
    nce_context.coordinate(
        nce_file_context,
        stage="export",
        status="completed",
        summary="Produtos exportaveis tiveram hash calculado e foram registrados pelo NCE.",
        formats=list(export_hashes.keys()),
        exports=len(export_hashes),
    )
    export_metadata["nce_context"] = nce_context.public_metadata()
    export_metadata["nce_file_context"] = nce_file_context.public_metadata()
    audit_manifest_path = export_audit_manifest(job_id, original_filename, export_metadata, export_hashes)
    if Path(audit_manifest_path).exists():
        export_paths["auditoria"] = audit_manifest_path
        export_hashes["auditoria"] = _sha256_file(Path(audit_manifest_path))
    _persist_reanalysis_state(
        job_id,
        {
            "schema": "ANON-REANALISE-DIRIGIDA-v1",
            "job_id": job_id,
            "original_filename": original_filename,
            "document_kind": options.document_kind.value,
            "model": options.model,
            "request_title": options.request_title,
            "source_sha256": sha256,
            "source_copy_path": str(source_copy_path),
            "original_text": original_text,
            "anonymized_text": anonymized_text,
            "control_table": [row.model_dump() for row in control_rows],
            "export_metadata": export_metadata,
            "export_sha256": export_hashes,
            "created_at": datetime.now().isoformat(timespec="seconds"),
        },
    )
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
            "sync_entries_loaded": len(options.sync_entries),
            "sync_entities_found": len(sync_entities),
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
    safe_summary["confidence_score"] = confidence.score
    safe_summary["confidence_level"] = confidence.level
    safe_summary["confidence_reasons"] = confidence.reasons
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
        review_items=review_items,
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
            ollama_json_rejection_reasons=ollama_metrics["json_rejection_reasons"],
            ollama_failure_reason=ollama_metrics["failure_reason"],
            ollama_preserved_items=ollama_metrics["preserved_items"],
            post_validation_warnings=post_validation.warnings,
            post_validation_score=post_validation.score,
            communication_events=trace.public_events(),
            communication_summary=trace.summary(),
            quality_status=quality.status,
            quality_score=quality.score,
            quality_reasons=quality.reasons,
            confidence_score=confidence.score,
            confidence_level=confidence.level,
            confidence_reasons=confidence.reasons,
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
    nce_context = NCEGroupContext.start(
        request_title=options.request_title,
        document_kind=options.document_kind,
        model=options.model,
    )
    replacement_state = nce_context.replacement_state
    results: list[AnonymizationResult] = []

    for path, original_filename in files:
        results.append(run_pipeline(path, original_filename, options, replacement_state, nce_context))

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
                f"NCE grupo: {nce_context.group_id}",
                f"NCE dicionario compartilhado: {len(nce_context.replacement_state.replacements)} entidade(s) canonica(s)",
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
                    "controle_sha256": result.audit.export_sha256.get("controle", ""),
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


def _safe_ollama_failure_reason(exc: Exception) -> str:
    message = " ".join(str(exc).split())
    if not message:
        return "IA local nao retornou resposta aproveitavel."
    return message[:240]


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


def _persist_source_copy(job_id: str, source_path: Path, original_filename: str) -> Path:
    suffix = Path(original_filename).suffix or source_path.suffix or ".bin"
    destination_dir = Path("data") / "sources" / job_id
    destination_dir.mkdir(parents=True, exist_ok=True)
    destination = destination_dir / f"original{suffix}"
    destination.write_bytes(source_path.read_bytes())
    return destination


def _persist_reanalysis_state(job_id: str, payload: dict[str, object]) -> None:
    export_dir = Path("data") / "exports" / job_id
    export_dir.mkdir(parents=True, exist_ok=True)
    (export_dir / "estado_reanalise.json").write_text(
        __import__("json").dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
