from dataclasses import dataclass, field

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

    for entity in sorted(entities, key=lambda item: item.start):
        original = text[entity.start : entity.end]
        if not original.strip():
            continue
        key = f"{entity.type.value}:{original.casefold()}"
        if key not in state.replacements:
            label = LABELS.get(entity.type.value, "DADO")
            state.counters[label] = state.counters.get(label, 0) + 1
            state.replacements[key] = f"[{label}_{state.counters[label]:03d}]"
        accepted.append((entity, key, original, state.replacements[key]))

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
