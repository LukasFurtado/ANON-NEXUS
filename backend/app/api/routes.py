from pathlib import Path
import hashlib
import json
from tempfile import NamedTemporaryFile
import urllib.error
import urllib.request

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse

from app.core.config import settings
from app.core.pipeline_state import load_pipeline_state
from app.core.safe_summary import load_safe_summary
from app.models.schemas import AnonymizeOptions, DocumentKind, ManualReanalysisRequest
from app.pipeline.manual_reanalysis import run_manual_reanalysis
from app.pipeline.runner import run_batch_pipeline, run_pipeline
from app.pipeline.sync_package import parse_sync_package, write_sync_package
from app.services.database import list_jobs
from app.services.diagnostic_chat import answer_diagnostic_question
from app.services.error_logger import ensure_error_log, log_error
from app.services.integrity_guard import IntegrityViolation, require_integrity, verify_integrity
from app.services.system_metrics import collect_system_metrics

router = APIRouter()


@router.get("/models")
def models() -> dict[str, object]:
    installed = _list_ollama_models()
    operational_model = settings.default_model
    assistant_model = settings.nexus_assistant_model
    recommended = [operational_model, assistant_model]
    provision_notes = _ensure_nexus_models(installed, operational_model, assistant_model)
    if provision_notes:
        installed = _list_ollama_models()
    merged = []
    for model in recommended + installed:
        if model not in merged:
            merged.append(model)
    operational_ready = _model_installed(operational_model, installed)
    assistant_ready = _model_installed(assistant_model, installed)
    return {
        "recommended": recommended,
        "installed": installed,
        "models": merged,
        "ollama_online": bool(installed),
        "operational_model": operational_model,
        "assistant_model": assistant_model,
        "operational_ready": operational_ready,
        "assistant_ready": assistant_ready,
        "provision_notes": provision_notes,
        "note": (
            "IA Nexus sincronizada com o Ollama."
            if operational_ready and assistant_ready
            else _models_pending_note(installed, provision_notes)
        ),
    }


@router.get("/system-metrics")
def system_metrics() -> dict[str, object]:
    return collect_system_metrics()


def _list_ollama_models() -> list[str]:
    request = urllib.request.Request(f"{settings.ollama_url}/api/tags", method="GET")
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return []

    names: list[str] = []
    for item in payload.get("models", []):
        name = item.get("name") or item.get("model")
        if isinstance(name, str) and name.lower() == "nexus-anon:latest":
            continue
        if isinstance(name, str) and name not in names:
            names.append(name)
    return names


def _model_installed(expected: str, installed: list[str]) -> bool:
    expected_normalized = expected.strip().lower()
    expected_without_tag = expected_normalized.split(":", 1)[0]
    for model in installed:
        current = model.strip().lower()
        if current == expected_normalized:
            return True
        if ":" not in current and current == expected_without_tag:
            return True
    return False


def _ensure_nexus_models(installed: list[str], operational_model: str, assistant_model: str) -> list[str]:
    if not installed:
        return []
    if not _model_installed("qwen3:32b", installed):
        return ["Modelo base qwen3:32b nao detectado no Ollama."]

    root = Path(__file__).resolve().parents[3]
    modelfiles = {
        operational_model: root / "resources" / "ollama" / "Modelfile.nexus.op",
        assistant_model: root / "resources" / "ollama" / "Modelfile.nexus-chat",
    }
    notes: list[str] = []
    for model, modelfile_path in modelfiles.items():
        if _model_installed(model, installed):
            continue
        if not modelfile_path.exists():
            notes.append(f"Modelfile local nao encontrado para {model}.")
            continue
        try:
            _create_ollama_model(model, modelfile_path)
            notes.append(f"Modelo {model} preparado automaticamente.")
        except Exception as exc:
            notes.append(f"Nao foi possivel preparar {model}: {exc}")
    return notes


def _create_ollama_model(model: str, modelfile_path: Path) -> None:
    payload = {
        "model": model,
        "modelfile": modelfile_path.read_text(encoding="utf-8"),
        "stream": False,
    }
    request = urllib.request.Request(
        f"{settings.ollama_url}/api/create",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        response.read()


def _models_pending_note(installed: list[str], provision_notes: list[str]) -> str:
    if _model_installed("qwen3:32b", installed):
        if provision_notes:
            return "IA Nexus ainda nao sincronizada. Tente atualizar o status; se persistir, verifique o log do sistema."
        return "qwen3:32b foi detectado. Clique em Atualizar status para preparar a IA Nexus especializada."
    return "Acione o Ollama e instale qwen3:32b para preparar nexus.op:latest e nexus-chat:latest."


@router.get("/integrity")
def integrity() -> dict[str, object]:
    status = verify_integrity()
    return {"ok": status.ok, "message": status.message, "checked_files": status.checked_files}


@router.get("/logs/errors")
def error_log() -> FileResponse:
    export_path = ensure_error_log()
    return FileResponse(export_path, filename="ANON_log_erros.txt", media_type="text/plain; charset=utf-8")


@router.get("/jobs")
def jobs() -> list[dict]:
    return list_jobs()


@router.get("/summary/{document_id}")
def safe_summary(document_id: str) -> dict:
    _enforce_integrity()
    summary = load_safe_summary(document_id)
    if not summary:
        raise HTTPException(status_code=404, detail="Resumo seguro nao encontrado.")
    return summary


@router.get("/pipeline-state/{pipeline_id}")
def pipeline_state(pipeline_id: str) -> dict:
    _enforce_integrity()
    state = load_pipeline_state(pipeline_id)
    if not state:
        raise HTTPException(status_code=404, detail="Estado do pipeline nao encontrado.")
    return state


@router.post("/diagnostics/chat")
async def diagnostics_chat(payload: dict) -> dict[str, str]:
    _enforce_integrity()
    return answer_diagnostic_question(payload)


@router.post("/anonymize")
async def anonymize(
    request: Request,
    file: UploadFile = File(...),
    sync_package: UploadFile | None = File(None),
    document_kind: DocumentKind = Form(...),
    model: str = Form("nexus.op:latest"),
    use_ollama: bool = Form(True),
    request_title: str | None = Form(None),
) -> dict:
    _enforce_integrity()
    model = settings.default_model
    sync_entries = _read_sync_entries(sync_package)
    suffix = Path(file.filename or "documento.txt").suffix
    with NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(await file.read())
        tmp_path = Path(tmp.name)

    try:
        result = run_pipeline(
            tmp_path,
            original_filename=file.filename or tmp_path.name,
            options=AnonymizeOptions(
                document_kind=document_kind,
                model=model,
                use_ollama=use_ollama,
                request_title=request_title,
                sync_entries=sync_entries,
            ),
        )
    except ValueError as exc:
        log_error(
            str(exc),
            stage="anonimizacao_individual",
            request_title=request_title,
            model=model,
            document_kind=document_kind.value,
            filenames=[file.filename or tmp_path.name],
            client_host=request.client.host if request.client else None,
            exception=exc,
            extra=_diagnostic_context(request, model, [(tmp_path, file.filename or tmp_path.name)]),
        )
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        log_error(
            f"Falha no processamento local: {exc}",
            stage="anonimizacao_individual",
            request_title=request_title,
            model=model,
            document_kind=document_kind.value,
            filenames=[file.filename or tmp_path.name],
            client_host=request.client.host if request.client else None,
            exception=exc,
            extra=_diagnostic_context(request, model, [(tmp_path, file.filename or tmp_path.name)]),
        )
        raise HTTPException(status_code=500, detail=f"Falha no processamento local: {exc}") from exc
    finally:
        tmp_path.unlink(missing_ok=True)

    return result.model_dump()


@router.post("/anonymize-batch")
async def anonymize_batch(
    request: Request,
    files: list[UploadFile] = File(...),
    sync_package: UploadFile | None = File(None),
    document_kind: DocumentKind = Form(...),
    model: str = Form("nexus.op:latest"),
    use_ollama: bool = Form(True),
    request_title: str | None = Form(None),
) -> dict:
    _enforce_integrity()
    model = settings.default_model
    sync_entries = _read_sync_entries(sync_package)
    if not files:
        message = "Nenhum arquivo enviado."
        log_error(
            message,
            stage="validacao_envio_lote",
            request_title=request_title,
            model=model,
            document_kind=document_kind.value,
            client_host=request.client.host if request.client else None,
            extra=_diagnostic_context(request, model, []),
        )
        raise HTTPException(status_code=400, detail=message)
    if len(files) > 3:
        message = "Limite de 3 arquivos por solicitacao."
        log_error(
            message,
            stage="validacao_envio_lote",
            request_title=request_title,
            model=model,
            document_kind=document_kind.value,
            filenames=[file.filename or "documento" for file in files],
            client_host=request.client.host if request.client else None,
            extra=_diagnostic_context(request, model, []),
        )
        raise HTTPException(status_code=400, detail=message)

    temporary_files: list[tuple[Path, str]] = []
    try:
        for file in files:
            suffix = Path(file.filename or "documento.txt").suffix
            with NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(await file.read())
                tmp_path = Path(tmp.name)
            temporary_files.append((tmp_path, file.filename or tmp_path.name))

        result = run_batch_pipeline(
            temporary_files,
            options=AnonymizeOptions(
                document_kind=document_kind,
                model=model,
                use_ollama=use_ollama,
                request_title=request_title,
                sync_entries=sync_entries,
            ),
            client_host=request.client.host if request.client else None,
        )
    except ValueError as exc:
        log_error(
            str(exc),
            stage="anonimizacao_lote",
            request_title=request_title,
            model=model,
            document_kind=document_kind.value,
            filenames=[filename for _, filename in temporary_files] or [file.filename or "documento" for file in files],
            client_host=request.client.host if request.client else None,
            exception=exc,
            extra=_diagnostic_context(request, model, temporary_files),
        )
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        log_error(
            f"Falha no processamento local: {exc}",
            stage="anonimizacao_lote",
            request_title=request_title,
            model=model,
            document_kind=document_kind.value,
            filenames=[filename for _, filename in temporary_files] or [file.filename or "documento" for file in files],
            client_host=request.client.host if request.client else None,
            exception=exc,
            extra=_diagnostic_context(request, model, temporary_files),
        )
        raise HTTPException(status_code=500, detail=f"Falha no processamento local: {exc}") from exc
    finally:
        for tmp_path, _ in temporary_files:
            tmp_path.unlink(missing_ok=True)

    return result.model_dump()


@router.get("/exports/{job_id}/original")
def export_original(job_id: str) -> FileResponse:
    _enforce_integrity()
    source_dir = Path("data") / "sources" / job_id
    candidates = [path for path in source_dir.glob("original.*") if path.is_file()]
    if not candidates:
        message = "Arquivo original preservado nao encontrado."
        log_error(message, stage="download_original", extra={"job_id": job_id})
        raise HTTPException(status_code=404, detail=message)
    source_path = candidates[0]
    state_path = Path("data") / "exports" / job_id / "estado_reanalise.json"
    original_filename = f"original{source_path.suffix}"
    if state_path.exists():
        try:
            import json

            state = json.loads(state_path.read_text(encoding="utf-8"))
            original_filename = str(state.get("original_filename") or original_filename)
        except Exception:
            original_filename = f"original{source_path.suffix}"
    return FileResponse(source_path, filename=original_filename)


@router.get("/exports/{job_id}/{format_name}")
def export(job_id: str, format_name: str) -> FileResponse:
    _enforce_integrity()
    special_files = {
        "avisos": "avisos.pdf",
        "controle": "controle_interno.pdf",
        "auditoria": "auditoria_interna.json",
        "reanalise_log": "log_reanalise_dirigida.txt",
    }
    filename = special_files.get(format_name, f"anonimizado.{format_name}")
    export_path = Path("data") / "exports" / job_id / filename
    if not export_path.exists():
        message = "Arquivo exportado nao encontrado."
        log_error(message, stage="download_produto", extra={"job_id": job_id, "formato": format_name})
        raise HTTPException(status_code=404, detail=message)
    download_name = {
        "avisos": "avisos.pdf",
        "controle": "controle_interno_anon.pdf",
        "auditoria": "auditoria_interna_anon.json",
        "reanalise_log": "log_reanalise_dirigida.txt",
    }.get(format_name, filename)
    return FileResponse(export_path, filename=download_name)


@router.get("/exports/groups/{group_id}/log")
def export_group_log(group_id: str) -> FileResponse:
    _enforce_integrity()
    export_path = Path("data") / "exports" / group_id / "log_processamento.pdf"
    if not export_path.exists():
        message = "Log de processamento nao encontrado."
        log_error(message, stage="download_log_processamento", extra={"group_id": group_id})
        raise HTTPException(status_code=404, detail=message)
    return FileResponse(export_path, filename="log_processamento_nexus_anon.pdf")


@router.get("/jobs/{job_id}/sync-package")
def sync_package(job_id: str) -> FileResponse:
    _enforce_integrity()
    try:
        export_path = write_sync_package(job_id)
    except ValueError as exc:
        log_error(str(exc), stage="pacote_sincronizacao", extra={"job_id": job_id})
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return FileResponse(export_path, filename="pacote_sincronizacao_anon.json", media_type="application/json")


@router.post("/jobs/{job_id}/manual-reanalysis")
def manual_reanalysis(job_id: str, payload: ManualReanalysisRequest) -> dict:
    _enforce_integrity()
    try:
        result = run_manual_reanalysis(job_id, payload.corrections, payload.note)
    except ValueError as exc:
        log_error(str(exc), stage="reanalise_dirigida", extra={"job_id": job_id})
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        log_error(f"Falha na reanalise dirigida: {exc}", stage="reanalise_dirigida", exception=exc, extra={"job_id": job_id})
        raise HTTPException(status_code=500, detail=f"Falha na reanalise dirigida: {exc}") from exc
    return result.model_dump()


def _read_sync_entries(sync_package: UploadFile | None):
    if not sync_package:
        return []
    content = sync_package.file.read()
    if not content:
        return []
    try:
        return parse_sync_package(content, sync_package.filename)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Pacote de sincronizacao invalido: {exc}") from exc


def _diagnostic_context(request: Request, selected_model: str, files: list[tuple[Path, str]]) -> dict[str, object]:
    installed_models = _list_ollama_models()
    return {
        "rota": f"{request.method} {request.url.path}",
        "url_ollama": settings.ollama_url,
        "ollama_online": bool(installed_models),
        "modelo_selecionado_instalado": selected_model in installed_models,
        "modelos_ollama_detectados": installed_models,
        "arquivos_diagnostico": [_file_diagnostic(path, filename) for path, filename in files],
    }


def _file_diagnostic(path: Path, filename: str) -> dict[str, object]:
    exists = path.exists()
    return {
        "nome": filename,
        "extensao": path.suffix.lower() or "sem extensao",
        "tamanho_bytes": path.stat().st_size if exists else "arquivo temporario indisponivel",
        "sha256": _sha256_file(path) if exists else "arquivo temporario indisponivel",
    }


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _enforce_integrity() -> None:
    try:
        require_integrity()
    except IntegrityViolation as exc:
        log_error(str(exc), stage="protecao_de_dados")
        raise HTTPException(status_code=423, detail=str(exc)) from exc
