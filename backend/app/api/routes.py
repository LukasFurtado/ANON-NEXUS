from pathlib import Path
import json
from tempfile import NamedTemporaryFile
import urllib.error
import urllib.request

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse

from app.core.config import settings
from app.models.schemas import AnonymizeOptions, DocumentKind
from app.pipeline.runner import run_batch_pipeline, run_pipeline
from app.services.database import list_jobs

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


@router.get("/jobs")
def jobs() -> list[dict]:
    return list_jobs()


@router.post("/anonymize")
async def anonymize(
    file: UploadFile = File(...),
    document_kind: DocumentKind = Form(...),
    model: str = Form("qwen3:32b"),
    use_ollama: bool = Form(True),
    request_title: str | None = Form(None),
) -> dict:
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
        raise HTTPException(status_code=400, detail=str(exc)) from exc
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
    if not files:
        raise HTTPException(status_code=400, detail="Nenhum arquivo enviado.")
    if len(files) > 3:
        raise HTTPException(status_code=400, detail="Limite de 3 arquivos por solicitacao.")

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
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Falha no processamento local: {exc}") from exc
    finally:
        for tmp_path, _ in temporary_files:
            tmp_path.unlink(missing_ok=True)

    return result.model_dump()


@router.get("/exports/{job_id}/{format_name}")
def export(job_id: str, format_name: str) -> FileResponse:
    export_path = Path("data") / "exports" / job_id / f"anonimizado.{format_name}"
    if not export_path.exists():
        raise HTTPException(status_code=404, detail="Arquivo exportado nao encontrado.")
    return FileResponse(export_path)


@router.get("/exports/groups/{group_id}/log")
def export_group_log(group_id: str) -> FileResponse:
    export_path = Path("data") / "exports" / group_id / "log_processamento.pdf"
    if not export_path.exists():
        raise HTTPException(status_code=404, detail="Log de processamento nao encontrado.")
    return FileResponse(export_path, filename="log_processamento_nexus_anon.pdf")
