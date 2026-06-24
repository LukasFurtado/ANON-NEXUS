import re

from app.models.schemas import DocumentKind, Entity, EntityType
from app.pipeline.delos_rules import documento_e_delos, should_preserve_entity
from app.pipeline.profile_strategy import profile_output_terms, profile_protected_patterns
from app.services.knowledge_base import protected_terms_for_profile


DATE_PATTERN = re.compile(r"\b\d{1,2}/\d{1,2}/\d{2,4}\b")
VALUE_PATTERN = re.compile(r"\bR\$\s?\d{1,3}(?:\.\d{3})*,\d{2}\b")
LEGAL_PATTERN = re.compile(r"\b(?:art\.|artigo|lei|decreto|jurisprud[eê]ncia)\b", re.I)
GENERIC_PROTOCOL_PATTERN = re.compile(
    r"^(?:processo administrativo|inquerito policial|inqu[ée]rito policial|relatorio|relat[óo]rio|oficio|of[íi]cio)$",
    re.I,
)
PROFILE_ENTITY_TYPES_ALLOWED_WITH_TERMS = {
    EntityType.pix,
    EntityType.bank_account,
    EntityType.bank_branch,
    EntityType.boleto,
    EntityType.card,
    EntityType.protocol,
    EntityType.proceeding,
    EntityType.functional_id,
}


def validate_entities(
    text: str,
    entities: list[Entity],
    document_kind: DocumentKind,
) -> tuple[list[Entity], int, int, list[str]]:
    valid: list[Entity] = []
    preserved_dates = 0
    preserved_values = 0
    warnings: list[str] = []
    delos_active = document_kind == DocumentKind.extrato_bancario and documento_e_delos(text)
    knowledge_protected_terms = [item.lower() for item in protected_terms_for_profile(document_kind)]

    for entity in entities:
        fragment = text[entity.start : entity.end]
        normalized_fragment = fragment.lower()
        if delos_active:
            preserve, reason = should_preserve_entity(fragment, _line_context(text, entity.start, entity.end), entity.type)
            if preserve:
                warnings.append(f"Marcacao preservada no perfil extrato_bancario: {reason}.")
                continue
        if DATE_PATTERN.fullmatch(fragment.strip()):
            preserved_dates += 1
            continue
        if VALUE_PATTERN.fullmatch(fragment.strip()):
            preserved_values += 1
            continue
        if LEGAL_PATTERN.search(fragment):
            warnings.append(f"Marcacao descartada por conter termo juridico: {fragment[:40]}")
            continue
        if GENERIC_PROTOCOL_PATTERN.fullmatch(fragment.strip()):
            warnings.append(f"Marcacao descartada por conter termo generico do perfil: {fragment[:40]}")
            continue
        if (
            entity.type not in PROFILE_ENTITY_TYPES_ALLOWED_WITH_TERMS
            and any(pattern.search(fragment) for pattern in profile_protected_patterns(document_kind))
        ):
            warnings.append(f"Marcacao descartada por conter termo protegido do perfil {document_kind.value}: {fragment[:40]}")
            continue
        if (
            entity.type not in PROFILE_ENTITY_TYPES_ALLOWED_WITH_TERMS
            and any(term and term in normalized_fragment for term in knowledge_protected_terms)
        ):
            warnings.append(f"Marcacao descartada por conter termo protegido da base operacional {document_kind.value}: {fragment[:40]}")
            continue
        valid.append(entity)

    return valid, preserved_dates, preserved_values, warnings


def validate_output(original: str, anonymized: str, document_kind: DocumentKind) -> list[str]:
    warnings: list[str] = []
    original_values = set(VALUE_PATTERN.findall(original))
    anonymized_values = set(VALUE_PATTERN.findall(anonymized))
    missing_values = original_values - anonymized_values
    if missing_values:
        warnings.append(f"Valores possivelmente alterados: {len(missing_values)}")
    original_dates = set(DATE_PATTERN.findall(original))
    anonymized_dates = set(DATE_PATTERN.findall(anonymized))
    missing_dates = original_dates - anonymized_dates
    if missing_dates:
        warnings.append(f"Datas possivelmente alteradas: {len(missing_dates)}")
    for pattern in profile_output_terms(document_kind):
        original_matches = _match_texts(pattern, original)
        anonymized_matches = _match_texts(pattern, anonymized)
        missing_matches = original_matches - anonymized_matches
        if missing_matches:
            warnings.append(f"Termos protegidos do perfil possivelmente alterados: {len(missing_matches)}")
    return warnings


def _match_texts(pattern: re.Pattern[str], text: str) -> set[str]:
    return {match.group(0) for match in pattern.finditer(text)}


def _line_context(text: str, start: int, end: int) -> str:
    line_start = text.rfind("\n", 0, start) + 1
    line_end = text.find("\n", end)
    if line_end == -1:
        line_end = len(text)
    return text[line_start:line_end]
