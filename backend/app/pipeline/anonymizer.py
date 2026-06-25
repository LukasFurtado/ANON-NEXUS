from dataclasses import dataclass, field
import re

from app.models.schemas import AnonymizationControlRow, Entity


LABELS = {
    "PERSON": "PESSOA",
    "ORGANIZATION": "EMPRESA",
    "CPF": "CPF",
    "CNPJ": "CNPJ",
    "RG": "RG",
    "CNH": "CNH",
    "PASSPORT": "PASSAPORTE",
    "PIS_NIS": "PIS_NIS",
    "FUNCTIONAL_ID": "MATRICULA",
    "BANK_ACCOUNT": "CONTA",
    "BANK_BRANCH": "AGENCIA",
    "PIX": "PIX",
    "BOLETO": "BOLETO",
    "CARD": "CARTAO",
    "PHONE": "TELEFONE",
    "EMAIL": "EMAIL",
    "ADDRESS": "ENDERECO",
    "CEP": "CEP",
    "VEHICLE_PLATE": "PLACA",
    "RENAVAM": "RENAVAM",
    "CHASSIS": "CHASSI",
    "IP": "IP",
    "MAC": "MAC",
    "QR_CODE": "QRCODE",
    "PROTOCOL": "PROTOCOLO",
    "PROCEEDING": "PROCESSO",
    "OTHER_IDENTIFIER": "IDENTIFICADOR",
}

TYPE_LABELS = {
    "PERSON": "Pessoa",
    "ORGANIZATION": "Empresa",
    "CPF": "CPF",
    "CNPJ": "CNPJ",
    "RG": "RG",
    "CNH": "CNH",
    "PASSPORT": "Passaporte",
    "PIS_NIS": "PIS/NIS",
    "FUNCTIONAL_ID": "Matricula funcional",
    "BANK_ACCOUNT": "Conta bancaria",
    "BANK_BRANCH": "Agencia bancaria",
    "PIX": "PIX",
    "BOLETO": "Boleto",
    "CARD": "Cartao",
    "PHONE": "Telefone",
    "EMAIL": "E-mail",
    "ADDRESS": "Endereco",
    "CEP": "CEP",
    "VEHICLE_PLATE": "Veiculo",
    "RENAVAM": "RENAVAM",
    "CHASSIS": "Chassi",
    "IP": "IP",
    "MAC": "MAC Address",
    "QR_CODE": "QR Code",
    "PROTOCOL": "Protocolo",
    "PROCEEDING": "Processo",
    "OTHER_IDENTIFIER": "Identificador",
}


@dataclass
class ReplacementState:
    counters: dict[str, int] = field(default_factory=dict)
    replacements: dict[str, str] = field(default_factory=dict)


@dataclass
class AppliedReplacement:
    key: str
    original: str
    entity_type: str
    entity_label: str
    anonymous_id: str
    first_start: int
    count: int = 0


def apply_anonymization(
    text: str,
    entities: list[Entity],
    state: ReplacementState | None = None,
) -> tuple[str, int, list[AnonymizationControlRow]]:
    state = state or ReplacementState()
    output = text
    applied = 0
    applied_by_key: dict[str, AppliedReplacement] = {}
    accepted: list[tuple[Entity, str, str, str]] = []
    occupied_spans: list[tuple[int, int]] = []

    for entity in sorted(entities, key=_entity_priority):
        if _overlaps_existing(entity.start, entity.end, occupied_spans):
            continue
        original = text[entity.start : entity.end]
        if not original.strip():
            continue
        key = _replacement_key(entity.type.value, original)
        if key not in state.replacements:
            label = LABELS.get(entity.type.value, "DADO")
            state.counters[label] = state.counters.get(label, 0) + 1
            state.replacements[key] = f"[{label}_{state.counters[label]:03d}]"
        accepted.append((entity, key, original, state.replacements[key]))
        occupied_spans.append((entity.start, entity.end))

    for entity, key, original, anonymous_id in sorted(accepted, key=lambda item: item[0].start, reverse=True):
        output = output[: entity.start] + anonymous_id + output[entity.end :]
        applied += 1
        if key not in applied_by_key:
            applied_by_key[key] = AppliedReplacement(
                key=key,
                original=original,
                entity_type=entity.type.value,
                entity_label=TYPE_LABELS.get(entity.type.value, entity.type.value),
                anonymous_id=anonymous_id,
                first_start=entity.start,
                count=0,
            )
        applied_by_key[key].count += 1

    for item in sorted(applied_by_key.values(), key=lambda row: row.first_start):
        output, extra_count = _replace_remaining_occurrences(output, item.original, item.anonymous_id, item.entity_type)
        if extra_count:
            item.count += extra_count
            applied += extra_count

    control_rows = [
        AnonymizationControlRow(
            original_value=item.original,
            entity_type=item.entity_label,
            anonymous_id=item.anonymous_id,
            occurrences=item.count,
        )
        for item in sorted(applied_by_key.values(), key=lambda row: row.first_start)
        if item.count > 0
    ]

    return output, applied, control_rows


def _replace_remaining_occurrences(text: str, original: str, anonymous_id: str, entity_type: str) -> tuple[str, int]:
    if not original.strip() or original == anonymous_id:
        return text, 0
    if not _can_replace_globally(original, entity_type):
        return text, 0

    pattern = re.compile(rf"(?<![\w\[\]]){re.escape(original)}(?![\w\[\]])")
    return pattern.subn(anonymous_id, text)


ENTITY_PRIORITY = {
    "CPF": 0,
    "CNPJ": 1,
    "BANK_ACCOUNT": 2,
    "BANK_BRANCH": 3,
    "PIX": 4,
    "EMAIL": 5,
    "PERSON": 6,
    "ORGANIZATION": 7,
    "OTHER_IDENTIFIER": 8,
    "PHONE": 9,
}


def _entity_priority(entity: Entity) -> tuple[int, int, int]:
    return (entity.start, ENTITY_PRIORITY.get(entity.type.value, 50), -(entity.end - entity.start))


def _overlaps_existing(start: int, end: int, occupied_spans: list[tuple[int, int]]) -> bool:
    return any(start < occupied_end and end > occupied_start for occupied_start, occupied_end in occupied_spans)


def _can_replace_globally(original: str, entity_type: str) -> bool:
    clean = original.strip()
    digits = re.sub(r"\D", "", clean)
    if len(clean) < 5:
        return False
    if digits and len(digits) >= max(3, len(clean) - 2):
        return False
    return entity_type in {"PERSON", "ORGANIZATION", "EMAIL", "ADDRESS", "PIX"}


def _replacement_key(entity_type: str, original: str) -> str:
    from app.core.nce import canonical_entity_key

    return canonical_entity_key(entity_type, original)
