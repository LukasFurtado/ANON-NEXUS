from dataclasses import dataclass, field
from typing import Any


@dataclass
class ConfidenceResult:
    score: int
    level: str
    reasons: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {"score": self.score, "level": self.level, "reasons": list(self.reasons)}


def compute_confidence(
    *,
    replacements_applied: int,
    validation_warnings: list[str],
    post_validation: dict[str, Any],
    ollama_metrics: dict[str, Any],
    structure_preserved: bool,
    ocr_used: bool,
) -> ConfidenceResult:
    score = 100
    reasons: list[str] = []

    if replacements_applied <= 0:
        score -= 35
        reasons.append("Nenhuma substituicao foi aplicada.")
    if validation_warnings:
        penalty = min(30, len(validation_warnings) * 4)
        score -= penalty
        reasons.append(f"Ha {len(validation_warnings)} aviso(s) de validacao.")

    residuals = int(post_validation.get("residual_entities") or 0)
    if residuals:
        score -= min(40, residuals * 10)
        reasons.append(f"Pos-validacao indicou {residuals} possivel(is) identificador(es) remanescente(s).")

    structure_warnings = int(post_validation.get("structure_warnings") or 0)
    if structure_warnings:
        score -= min(25, structure_warnings * 12)
        reasons.append("Ha ressalva de preservacao estrutural.")

    if int(ollama_metrics.get("json_rejected_chunks") or 0):
        score -= min(20, int(ollama_metrics.get("json_rejected_chunks") or 0) * 8)
        reasons.append("A IA local retornou bloco(s) JSON recusado(s).")
    if ollama_metrics.get("failure_reason"):
        score -= 25
        reasons.append("A IA local precisou de fallback auditavel.")
    if not structure_preserved:
        score -= 10
        reasons.append("Preservacao estrutural nao foi confirmada.")
    if ocr_used:
        score -= 5
        reasons.append("OCR foi utilizado; conferir visualmente o texto recuperado.")

    score = max(0, min(100, score))
    if score >= 85:
        level = "ALTA"
    elif score >= 65:
        level = "MEDIA"
    else:
        level = "BAIXA"
    if not reasons:
        reasons.append("Nenhuma ressalva objetiva de confiabilidade foi identificada.")
    return ConfidenceResult(score=score, level=level, reasons=reasons)
