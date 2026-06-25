from __future__ import annotations

import hashlib
import json
import re
import tempfile
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

from app.core.config import settings


OFFLINE_MODE = "OFFLINE"
ENRICHMENT_MODE = "ENRIQUECIMENTO"


class HybridSecurityError(RuntimeError):
    pass


@dataclass(frozen=True)
class PublicSource:
    key: str
    label: str
    base_url: str
    download_url: str
    description: str
    target_filename: str
    provider_type: str = "public_dataset"
    enabled_by_default: bool = True


@dataclass
class HybridSecurityManager:
    mode: str | None = None
    enrichment_enabled: bool | None = None
    events: list[dict] = field(default_factory=list)

    def __post_init__(self) -> None:
        configured_mode = (self.mode or settings.hybrid_default_mode or OFFLINE_MODE).upper()
        if configured_mode not in {OFFLINE_MODE, ENRICHMENT_MODE}:
            configured_mode = OFFLINE_MODE
        self.mode = configured_mode
        if self.enrichment_enabled is None:
            self.enrichment_enabled = bool(settings.hybrid_enrichment_enabled)
        if self.mode == ENRICHMENT_MODE and not self.enrichment_enabled:
            self.mode = OFFLINE_MODE

    def status(self) -> dict[str, object]:
        return {
            "mode": self.mode,
            "processing_allowed": self.mode == OFFLINE_MODE,
            "enrichment_enabled": self.enrichment_enabled,
            "public_sources": [source.__dict__ for source in allowed_public_sources()],
            "blocked_external_apis": blocked_external_api_requests(),
            "security_policy": {
                "default_mode": OFFLINE_MODE,
                "documents_online": "blocked",
                "uploads": "blocked",
                "automatic_downloads": "disabled",
                "allowed_network_direction": "download_public_data_only",
            },
        }

    def run_automatic_downloads(self, source_keys: list[str] | None = None) -> dict[str, object]:
        self.begin_enrichment()
        known_keys = {source.key for source in allowed_public_sources()}
        unknown_keys = [key for key in (source_keys or []) if key not in known_keys]
        if unknown_keys:
            self.force_offline()
            raise HybridSecurityError(f"Fonte publica nao autorizada: {', '.join(unknown_keys)}")
        selected_sources = [
            source for source in allowed_public_sources()
            if (source_keys and source.key in source_keys) or (not source_keys and source.enabled_by_default)
        ]
        results: list[dict[str, object]] = []
        try:
            for source in selected_sources:
                results.append(self.download_public_source(source))
            return {
                "success": all(item.get("success") for item in results),
                "mode": OFFLINE_MODE,
                "downloads": results,
                "message": "Atualizacao de dados publicos concluida; ANON retornou ao modo OFFLINE.",
            }
        finally:
            self.force_offline()

    def download_public_source(self, source: PublicSource) -> dict[str, object]:
        if self.mode != ENRICHMENT_MODE:
            raise HybridSecurityError("Downloads publicos exigem modo ENRIQUECIMENTO.")
        if not self.validate_public_source_url(source.download_url):
            raise HybridSecurityError(f"Fonte publica fora da whitelist: {source.download_url}")

        request = urllib.request.Request(
            source.download_url,
            headers={"User-Agent": "ANON-local-enrichment/1.0"},
            method="GET",
        )
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                payload = response.read()
        except (urllib.error.URLError, TimeoutError) as exc:
            self._log_event("download_failed", f"Falha ao baixar {source.key}: {exc}")
            return {
                "success": False,
                "source": source.key,
                "error": str(exc),
            }

        if not self.validate_download_content(payload):
            self._log_event("download_blocked", f"Conteudo bloqueado por padrao sensivel: {source.key}")
            return {
                "success": False,
                "source": source.key,
                "error": "Conteudo bloqueado por conter padrao sensivel.",
            }

        manifest = self.build_download_manifest(source.key, payload)
        target_dir = settings.data_dir / "public_sources"
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / source.target_filename
        manifest_path = target_path.with_suffix(target_path.suffix + ".manifest.json")

        with tempfile.NamedTemporaryFile(delete=False, dir=target_dir, suffix=".tmp") as tmp:
            tmp.write(payload)
            tmp_path = Path(tmp.name)
        tmp_path.replace(target_path)
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        self._log_event("download_ok", f"Dados publicos atualizados: {source.key}")
        return {
            "success": True,
            "source": source.key,
            "path": str(target_path),
            "manifest": str(manifest_path),
            "sha256": manifest["sha256"],
            "bytes": manifest["bytes"],
        }

    def require_offline_processing(self) -> None:
        if self.mode != OFFLINE_MODE:
            self._log_event("blocked_processing", "Documento bloqueado fora do modo offline.")
            self.force_offline()
            raise HybridSecurityError(
                "Processamento bloqueado: documentos sigilosos so podem ser anonimizados em modo OFFLINE."
            )

    def begin_enrichment(self) -> None:
        if not self.enrichment_enabled:
            self._log_event("blocked_enrichment", "Enriquecimento online desabilitado por configuracao.")
            raise HybridSecurityError(
                "Enriquecimento online desabilitado. O ANON permanece em modo OFFLINE."
            )
        self.mode = ENRICHMENT_MODE
        self._log_event("mode_enrichment", "Modo de enriquecimento ativado para dados publicos.")

    def force_offline(self) -> None:
        self.mode = OFFLINE_MODE
        self._log_event("mode_offline", "Modo offline restaurado.")

    def validate_public_source_url(self, url: str) -> bool:
        parsed = urlparse(url)
        if parsed.scheme != "https":
            return False
        return any(url.startswith(source.base_url) for source in allowed_public_sources())

    def validate_download_content(self, payload: bytes) -> bool:
        sample = payload[:200000].decode("utf-8", errors="ignore")
        return not contains_sensitive_pattern(sample)

    def build_download_manifest(self, source_key: str, payload: bytes) -> dict[str, object]:
        source = next((item for item in allowed_public_sources() if item.key == source_key), None)
        if source is None:
            raise HybridSecurityError(f"Fonte publica nao autorizada: {source_key}")
        return {
            "source": source.__dict__,
            "sha256": hashlib.sha256(payload).hexdigest().upper(),
            "bytes": len(payload),
            "created_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "mode": ENRICHMENT_MODE,
            "note": "Manifesto de dados publicos. Documentos do usuario nao participam deste fluxo.",
        }

    def _log_event(self, event: str, message: str) -> None:
        entry = {
            "timestamp": datetime.now(UTC).isoformat(timespec="seconds"),
            "event": event,
            "message": message,
            "mode": self.mode,
        }
        self.events.append(entry)
        _append_hybrid_audit(entry)


def allowed_public_sources() -> list[PublicSource]:
    return [
        PublicSource(
            "ibge_municipios",
            "IBGE - Municipios",
            "https://servicodados.ibge.gov.br",
            "https://servicodados.ibge.gov.br/api/v1/localidades/municipios",
            "Municipios brasileiros oficiais para biblioteca geografica local.",
            "ibge_municipios.json",
            "official_public_dataset",
            True,
        ),
        PublicSource(
            "ibge_estados",
            "IBGE - Estados",
            "https://servicodados.ibge.gov.br",
            "https://servicodados.ibge.gov.br/api/v1/localidades/estados",
            "Unidades da federacao para biblioteca geografica local.",
            "ibge_estados.json",
            "official_public_dataset",
            True,
        ),
        PublicSource(
            "brasilapi_banks",
            "BrasilAPI - Bancos",
            "https://brasilapi.com.br",
            "https://brasilapi.com.br/api/banks/v1",
            "Lista publica de bancos para biblioteca institucional/financeira local.",
            "brasilapi_banks.json",
            "public_aggregator_dataset",
            True,
        ),
    ]


def blocked_external_api_requests() -> list[dict[str, str]]:
    return [
        {
            "key": "cpf_lookup",
            "reason": "Consulta externa de CPF exigiria enviar identificador pessoal.",
            "policy": "bloqueado; validar CPF localmente por digito verificador.",
        },
        {
            "key": "cnpj_lookup_from_document",
            "reason": "CNPJ extraido de documento pode compor investigacao sigilosa.",
            "policy": "bloqueado no processamento; usar apenas bases publicas baixadas previamente.",
        },
        {
            "key": "cep_lookup_from_document",
            "reason": "CEP pode revelar endereco residencial ou local sensivel.",
            "policy": "bloqueado no processamento; ViaCEP fica apenas como referencia futura com dado manual nao sensivel.",
        },
        {
            "key": "openai_or_cloud_ai_document_processing",
            "reason": "Documento sigiloso nao pode ser enviado a IA externa.",
            "policy": "bloqueado; usar IA local pelo Ollama.",
        },
    ]


def contains_sensitive_pattern(value: str) -> bool:
    patterns = [
        r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b",
        r"\b\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}\b",
        r"\b(?:rua|avenida|travessa|logradouro)\s+[\w\s]{3,}",
        r"\b(?:investigad[oa]|vitima|testemunha|sigiloso|rif)\b",
    ]
    text = value.lower()
    return any(re.search(pattern, text, flags=re.I) for pattern in patterns)


def get_hybrid_security_manager() -> HybridSecurityManager:
    return HybridSecurityManager()


def _append_hybrid_audit(entry: dict) -> None:
    try:
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        audit_path = settings.data_dir / "hybrid_security_audit.jsonl"
        with audit_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError:
        return
