from dataclasses import dataclass
from typing import Any

from app.models.schemas import AnonymizationControlRow


@dataclass
class ReviewItem:
    id: str
    category: str
    label: str
    status: str
    recommendation: str
    severity: str = "media"
    metadata: dict[str, Any] | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "category": self.category,
            "label": self.label,
            "status": self.status,
            "recommendation": self.recommendation,
            "severity": self.severity,
            "metadata": self.metadata or {},
        }


def build_review_items(
    *,
    control_rows: list[AnonymizationControlRow],
    validation_warnings: list[str],
    post_validation: dict[str, Any],
    confidence: dict[str, Any],
) -> list[dict[str, Any]]:
    items: list[ReviewItem] = []
    for index, row in enumerate(control_rows[:100], start=1):
        items.append(
            ReviewItem(
                id=f"entity-{index}",
                category="entidade",
                label=f"{row.entity_type} -> {row.anonymous_id}",
                status="pendente",
                recommendation="Conferir se a substituicao corresponde ao dado sensivel correto.",
                severity="baixa",
                metadata={"occurrences": row.occurrences, "anonymous_id": row.anonymous_id},
            )
        )
    for index, warning in enumerate(validation_warnings[:50], start=1):
        items.append(
            ReviewItem(
                id=f"warning-{index}",
                category="aviso",
                label=_compact_warning(warning),
                status="pendente",
                recommendation="Revisar o ponto antes de uso externo do produto.",
                severity="alta" if "remanescente" in warning.lower() or "estrutura" in warning.lower() else "media",
            )
        )
    if int(post_validation.get("residual_entities") or 0):
        items.append(
            ReviewItem(
                id="post-validation-residuals",
                category="pos_validacao",
                label="Possiveis identificadores remanescentes detectados.",
                status="pendente",
                recommendation="Executar conferencia humana e, se necessario, anonimizar manualmente os pontos remanescentes.",
                severity="alta",
                metadata={"residual_by_type": post_validation.get("residual_by_type") or {}},
            )
        )
    if int(confidence.get("score") or 100) < 85:
        items.append(
            ReviewItem(
                id="confidence-review",
                category="confiabilidade",
                label=f"Confiabilidade {confidence.get('level', 'NAO INFORMADA')} ({confidence.get('score', 0)}/100)",
                status="pendente",
                recommendation="Revisao humana obrigatoria antes de uso institucional externo.",
                severity="alta" if int(confidence.get("score") or 0) < 65 else "media",
            )
        )
    return [item.as_dict() for item in items]


def _compact_warning(value: str, limit: int = 150) -> str:
    text = " ".join(str(value).split())
    if len(text) <= limit:
        return text
    return f"{text[: limit - 12].rstrip()}... [resumo]"
