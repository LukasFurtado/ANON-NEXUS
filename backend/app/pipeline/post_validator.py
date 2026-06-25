from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
import re

from app.models.schemas import DocumentKind, Entity
from app.pipeline.identifier_detectors import is_possible_truncated_cpf_digits
from app.pipeline.regex_rules import detect_entities_by_regex


@dataclass
class PostValidationResult:
    warnings: list[str] = field(default_factory=list)
    score: int = 100
    residual_entities: int = 0
    residual_by_type: dict[str, int] = field(default_factory=dict)
    structure_warnings: int = 0
    anonymous_markers: int = 0

    def as_dict(self) -> dict[str, object]:
        return {
            "warnings": list(self.warnings),
            "score": self.score,
            "residual_entities": self.residual_entities,
            "residual_by_type": dict(self.residual_by_type),
            "structure_warnings": self.structure_warnings,
            "anonymous_markers": self.anonymous_markers,
        }


def validate_post_anonymization(
    original_text: str,
    anonymized_text: str,
    document_kind: DocumentKind,
    original_filename: str | None = None,
) -> PostValidationResult:
    warnings: list[str] = []
    residuals = [
        entity
        for entity in detect_entities_by_regex(anonymized_text, document_kind, original_filename)
        if not _is_anonymous_marker(entity)
    ]
    by_type = Counter(entity.type.value for entity in residuals)
    if by_type:
        summary = ", ".join(f"{entity_type}={count}" for entity_type, count in sorted(by_type.items()))
        warnings.append(f"Possiveis identificadores remanescentes apos anonimizacao: {summary}.")

    truncated_cpf_warnings = _possible_truncated_cpf_warnings(anonymized_text)
    warnings.extend(truncated_cpf_warnings)

    structure_warnings = _csv_structure_warnings(original_text, anonymized_text, original_filename)
    structure_warnings.extend(_generic_structure_warnings(original_text, anonymized_text))
    warnings.extend(structure_warnings)
    anonymous_markers = len(ANON_MARKER_PATTERN.findall(anonymized_text))
    if residuals and anonymous_markers == 0:
        warnings.append("Nenhum marcador anonimo foi encontrado apesar de possiveis identificadores remanescentes.")

    score = 100
    score -= min(60, len(residuals) * 12)
    score -= min(20, len(truncated_cpf_warnings) * 8)
    score -= min(30, len(structure_warnings) * 15)
    if residuals and anonymous_markers == 0:
        score -= 10
    return PostValidationResult(
        warnings=warnings,
        score=max(0, score),
        residual_entities=len(residuals),
        residual_by_type=dict(sorted(by_type.items())),
        structure_warnings=len(structure_warnings),
        anonymous_markers=anonymous_markers,
    )


def _is_anonymous_marker(entity: Entity) -> bool:
    value = entity.text.strip()
    return value.startswith("[") and value.endswith("]") and "_" in value


def _csv_structure_warnings(original_text: str, anonymized_text: str, original_filename: str | None) -> list[str]:
    if Path(original_filename or "").suffix.lower() != ".csv":
        return []
    original_lines = original_text.splitlines()
    anonymized_lines = anonymized_text.splitlines()
    warnings: list[str] = []
    if len(original_lines) != len(anonymized_lines):
        warnings.append("Estrutura CSV possivelmente alterada: quantidade de linhas divergente.")
        return warnings
    for index, (original, anonymized) in enumerate(zip(original_lines, anonymized_lines), start=1):
        delimiter = ";" if original.count(";") >= original.count(",") else ","
        if delimiter not in original:
            continue
        if original.count(delimiter) != anonymized.count(delimiter):
            warnings.append(f"Estrutura CSV possivelmente alterada na linha {index}: quantidade de colunas divergente.")
            break
    return warnings


ANON_MARKER_PATTERN = re.compile(r"\[[A-Z_]+_\d{3}\]")
TRUNCATED_CPF_TOKEN_PATTERN = re.compile(r"(?<!\d)\d{10}(?!\d)")
CPF_CONTEXT_PATTERN = re.compile(r"\b(?:CPF|CPF/CNPJ|CPFCNPJ|cpfCnpj\w*)\b|\[CPF_\d{3}\]", re.I)
FULL_CPF_TOKEN_PATTERN = re.compile(r"(?<!\d)0?\d{3}\.?\d{3}\.?\d{3}-?\d{2}(?!\d)")


def _possible_truncated_cpf_warnings(text: str) -> list[str]:
    lines = text.splitlines()
    warnings: list[str] = []
    for line_number, line in enumerate(lines, start=1):
        context = "\n".join(lines[max(0, line_number - 2): min(len(lines), line_number + 1)])
        has_cpf_context = bool(CPF_CONTEXT_PATTERN.search(context) or FULL_CPF_TOKEN_PATTERN.search(context))
        if not has_cpf_context:
            continue
        possible_count = sum(
            1
            for match in TRUNCATED_CPF_TOKEN_PATTERN.finditer(line)
            if is_possible_truncated_cpf_digits(match.group(0))
        )
        if possible_count:
            warnings.append(
                f"Possivel CPF incompleto por zero inicial removido na linha {line_number}: "
                f"{possible_count} ocorrencia(s). Revisao humana recomendada."
            )
        if len(warnings) >= 20:
            warnings.append("Ha mais possiveis CPFs incompletos; revisar a base original e a exportacao da planilha.")
            break
    return warnings


def _generic_structure_warnings(original_text: str, anonymized_text: str) -> list[str]:
    warnings: list[str] = []
    original_lines = original_text.splitlines()
    anonymized_lines = anonymized_text.splitlines()
    if original_lines and abs(len(original_lines) - len(anonymized_lines)) > max(2, int(len(original_lines) * 0.05)):
        warnings.append("Estrutura textual possivelmente alterada: quantidade de linhas mudou de forma relevante.")
    if original_text and len(anonymized_text) < len(original_text) * 0.45:
        warnings.append("Texto anonimizado ficou muito menor que o original; revisar possivel perda de conteudo.")
    return warnings
