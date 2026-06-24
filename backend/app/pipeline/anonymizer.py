from app.models.schemas import Entity


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


def apply_anonymization(text: str, entities: list[Entity]) -> tuple[str, int]:
    counters: dict[str, int] = {}
    replacements: dict[str, str] = {}
    output = text
    applied = 0

    for entity in sorted(entities, key=lambda item: item.start, reverse=True):
        original = text[entity.start : entity.end]
        if not original.strip():
            continue
        key = f"{entity.type.value}:{original.casefold()}"
        if key not in replacements:
            label = LABELS.get(entity.type.value, "DADO")
            counters[label] = counters.get(label, 0) + 1
            replacements[key] = f"[{label}_{counters[label]:03d}]"
        output = output[: entity.start] + replacements[key] + output[entity.end :]
        applied += 1

    return output, applied
