from dataclasses import dataclass
from typing import Literal


QualityStatus = Literal["BOM", "REVISAR", "ATENCAO_CRITICA"]
REQUIRED_STAGES = {"parser", "ner", "regex", "substitution", "validation", "export"}


@dataclass
class QualityResult:
    status: QualityStatus
    reasons: list[str]
    score: int


def classify_quality(safe_summary: dict, profile: dict) -> QualityResult:
    critical: list[str] = []
    review: list[str] = []
    stages = set(safe_summary.get("pipeline_stages_ok") or [])
    warnings = [str(item) for item in safe_summary.get("warnings_raised") or []]

    missing = sorted(REQUIRED_STAGES - stages)
    if missing:
        critical.append(f"Etapas ausentes: {', '.join(missing)}")
    if any("critico" in warning.lower() or "nao resolvido" in warning.lower() for warning in warnings):
        critical.append("Aviso critico nao resolvido.")
    if int(safe_summary.get("total_entities_detected") or 0) == 0 and profile.get("anonymize_always"):
        critical.append("Nenhuma entidade detectada em perfil com campos obrigatorios de anonimização.")
    if warnings:
        review.append("Ha avisos que exigem revisao humana.")

    expected = max(1, len(profile.get("anonymize_always") or []))
    actual = int(safe_summary.get("total_entities_detected") or 0)
    if actual / expected < 0.85:
        review.append("Volume de entidades detectadas abaixo do esperado para o perfil.")

    score = max(0, 100 - 40 * len(critical) - 15 * len(review))
    if critical:
        return QualityResult(status="ATENCAO_CRITICA", reasons=critical + review, score=score)
    if review:
        return QualityResult(status="REVISAR", reasons=review, score=score)
    return QualityResult(status="BOM", reasons=["Nenhuma condição objetiva de revisão adicional foi identificada."], score=score)
