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
from app.models.schemas import AnonymizeOptions, DocumentKind
from app.pipeline.runner import run_batch_pipeline, run_pipeline
from app.services.database import list_jobs
from app.services.diagnostic_chat import answer_diagnostic_question
from app.services.error_logger import ensure_error_log, log_error
from app.services.integrity_guard import IntegrityViolation, require_integrity, verify_integrity

router = APIRouter()


@router.get("/models")
def models() -> dict[str, object]:
    installed = _list_ollama_models()
    recommended = ["qwen3:32b", "NEXUS-anon:latest", "gemma4:31b"]
    merged = []
    for model in recommended + installed:
        if model not in merged:
            merged.append(model)
    return {
        "recommended": recommended,
        "installed": installed,
        "models": merged,
        "ollama_online": bool(installed),
        "note": "Modelos sao detectados localmente pelo Ollama.",
    }


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
        if isinstance(name, str) and name not in names:
            names.append(name)
    return names


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
    document_kind: DocumentKind = Form(...),
    model: str = Form("qwen3:32b"),
    use_ollama: bool = Form(True),
    request_title: str | None = Form(None),
) -> dict:
    _enforce_integrity()
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
    document_kind: DocumentKind = Form(...),
    model: str = Form("qwen3:32b"),
    use_ollama: bool = Form(True),
    request_title: str | None = Form(None),
) -> dict:
    _enforce_integrity()
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


@router.get("/exports/{job_id}/{format_name}")
def export(job_id: str, format_name: str) -> FileResponse:
    _enforce_integrity()
    filename = "avisos.pdf" if format_name == "avisos" else f"anonimizado.{format_name}"
    export_path = Path("data") / "exports" / job_id / filename
    if not export_path.exists():
        message = "Arquivo exportado nao encontrado."
        log_error(message, stage="download_produto", extra={"job_id": job_id, "formato": format_name})
        raise HTTPException(status_code=404, detail=message)
    return FileResponse(export_path)


@router.get("/exports/groups/{group_id}/log")
def export_group_log(group_id: str) -> FileResponse:
    _enforce_integrity()
    export_path = Path("data") / "exports" / group_id / "log_processamento.pdf"
    if not export_path.exists():
        message = "Log de processamento nao encontrado."
        log_error(message, stage="download_log_processamento", extra={"group_id": group_id})
        raise HTTPException(status_code=404, detail=message)
    return FileResponse(export_path, filename="log_processamento_nexus_anon.pdf")


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
