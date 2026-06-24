import traceback
import platform
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from app.services.data_protection import PROTECTION_NOTICE
from app.version import APP_VERSION


ERROR_LOG_PATH = Path("data") / "logs" / "anon_erros.txt"


def log_error(
    message: str,
    *,
    stage: str,
    request_title: str | None = None,
    model: str | None = None,
    document_kind: str | None = None,
    filenames: list[str] | None = None,
    client_host: str | None = None,
    exception: BaseException | None = None,
    extra: dict[str, Any] | None = None,
) -> Path:
    ERROR_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    lines = [
        "=" * 90,
        "ANON - REGISTRO ACUMULATIVO DE ERRO",
        f"Data e hora: {timestamp}",
        f"Versao ANON: {APP_VERSION}",
        PROTECTION_NOTICE,
        f"Etapa: {stage}",
        f"Mensagem: {message}",
        f"Numero IP / Nome solicitacao: {request_title or 'Nao informado'}",
        f"Modelo local: {model or 'Nao informado'}",
        f"Perfil documental: {document_kind or 'Nao informado'}",
        f"Arquivos: {', '.join(filenames or []) if filenames else 'Nao informado'}",
        f"Host cliente: {client_host or 'Nao identificado'}",
        f"Diretorio de execucao: {Path.cwd()}",
        f"Python: {sys.version.split()[0]}",
        f"Sistema operacional: {platform.platform()}",
    ]
    if extra:
        for key, value in extra.items():
            lines.append(f"{key}: {_format_extra_value(value)}")
    if exception is not None:
        lines.extend(
            [
                "",
                "Detalhe tecnico resumido:",
                f"{type(exception).__name__}: {exception}",
                "",
                "Rastreamento tecnico:",
                "".join(traceback.format_exception(type(exception), exception, exception.__traceback__)).strip(),
            ]
        )
    lines.append("")
    with ERROR_LOG_PATH.open("a", encoding="utf-8") as file:
        file.write("\n".join(lines))
        file.write("\n")
    return ERROR_LOG_PATH


def _format_extra_value(value: Any) -> str:
    if isinstance(value, list):
        if not value:
            return "[]"
        return "\n" + "\n".join(f"  - {item}" for item in value)
    if isinstance(value, dict):
        if not value:
            return "{}"
        return "\n" + "\n".join(f"  - {key}: {item}" for key, item in value.items())
    return str(value)


def ensure_error_log() -> Path:
    ERROR_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not ERROR_LOG_PATH.exists():
        ERROR_LOG_PATH.write_text(
            "ANON - Log local de erros\n"
            "Este arquivo e acumulativo e registra falhas locais para apoio tecnico e auditoria operacional.\n"
            "Nao registra o conteudo integral dos documentos; registra metadados, hashes e contexto tecnico.\n\n",
            encoding="utf-8",
        )
    return ERROR_LOG_PATH
