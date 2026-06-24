import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


SUMMARY_DIR = Path("data") / "summaries"
SENSITIVE_PATTERN = re.compile(r"(?:\d{3}\.?\d{3}\.?\d{3}-?\d{2}|\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}|@)")


def generate_safe_summary(pipeline_result: dict[str, Any]) -> dict[str, Any]:
    original_text = str(pipeline_result.get("original_text") or "")
    original_tokens = _sample_tokens(original_text)
    entities = pipeline_result.get("entities") or []
    stats = pipeline_result.get("stats") or {}
    audit = pipeline_result.get("audit") or {}
    profile = str(pipeline_result.get("document_kind") or pipeline_result.get("profile") or "")
    source_hash = str(audit.get("source_sha256") or pipeline_result.get("document_id") or "")
    export_hashes = audit.get("export_sha256") if isinstance(audit.get("export_sha256"), dict) else {}
    warnings = [
        _sanitize_for_summary(str(item), original_tokens)
        for item in stats.get("validation_warnings", [])
    ]
    warnings = [item for item in warnings if item]

    by_type = Counter()
    for entity in entities:
        entity_type = entity.get("type") if isinstance(entity, dict) else getattr(entity, "type", "")
        by_type[str(getattr(entity_type, "value", entity_type))] += 1

    summary = {
        "document_id": source_hash,
        "profile": profile,
        "total_entities_detected": int(stats.get("entities_found") or len(entities)),
        "entities_by_type": dict(sorted(by_type.items())),
        "substitution_method_used": {
            "pseudonimizacao": int(stats.get("replacements_applied") or 0),
            "mascaramento": 0,
        },
        "fields_preserved": _safe_list(pipeline_result.get("profile_preserve_always") or []),
        "warnings_raised": warnings,
        "processing_duration_ms": int(float(audit.get("processing_time_seconds") or 0) * 1000),
        "integrity_hash_output": str(export_hashes.get("pdf") or export_hashes.get("txt") or next(iter(export_hashes.values()), "")),
        "pipeline_stages_ok": _safe_list(pipeline_result.get("pipeline_stages_ok") or []),
    }
    return summary


def persist_safe_summary(summary: dict[str, Any]) -> Path:
    SUMMARY_DIR.mkdir(parents=True, exist_ok=True)
    document_id = str(summary.get("document_id") or "sem_hash")
    path = SUMMARY_DIR / f"{document_id}.json"
    path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def load_safe_summary(document_id: str) -> dict[str, Any] | None:
    path = SUMMARY_DIR / f"{document_id}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _sanitize_for_summary(value: str, original_tokens: set[str] | None = None) -> str | None:
    cleaned = " ".join(value.split())
    if not cleaned or len(cleaned) > 40:
        return None
    if SENSITIVE_PATTERN.search(cleaned):
        return None
    if original_tokens:
        lowered = cleaned.lower()
        if any(token in lowered for token in original_tokens if len(token) >= 4):
            return None
    return cleaned


def _safe_list(values: list[Any]) -> list[str]:
    output: list[str] = []
    for value in values:
        sanitized = _sanitize_for_summary(str(value), set())
        if sanitized:
            output.append(sanitized)
    return output


def _sample_tokens(text: str, limit: int = 50) -> set[str]:
    tokens = re.findall(r"[A-Za-zÀ-ÿ0-9_.@-]{4,}", text.lower())
    return set(tokens[:limit])
