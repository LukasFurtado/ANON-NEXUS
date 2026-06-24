import re

from app.models.schemas import DocumentKind, Entity, EntityType
from app.pipeline.profile_strategy import profile_regex_patterns


PATTERNS: list[tuple[EntityType, re.Pattern[str]]] = [
    (EntityType.cpf, re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b")),
    (EntityType.cnpj, re.compile(r"\b\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}\b")),
    (EntityType.email, re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)),
    (EntityType.phone, re.compile(r"\b(?:\+?55\s?)?(?:\(?\d{2}\)?\s?)?(?:9\s?)?\d{4}[-\s]?\d{4}\b")),
    (EntityType.cep, re.compile(r"\b\d{5}-?\d{3}\b")),
    (EntityType.vehicle_plate, re.compile(r"\b[A-Z]{3}[-\s]?\d[A-Z0-9]\d{2}\b", re.I)),
    (EntityType.ip, re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")),
    (EntityType.mac, re.compile(r"\b(?:[0-9A-F]{2}[:-]){5}[0-9A-F]{2}\b", re.I)),
    (EntityType.card, re.compile(r"\b(?:\d[ -]*?){13,19}\b")),
    (EntityType.pix, re.compile(r"\b(?:PIX|CHAVE PIX|CHAVE)\s*[:\-]?\s*[\w.@+\-/]{8,}\b", re.I)),
    (EntityType.renavam, re.compile(r"\bRENAVAM\s*[:\-]?\s*\d{9,11}\b", re.I)),
    (EntityType.chassis, re.compile(r"\b[A-HJ-NPR-Z0-9]{17}\b", re.I)),
    (EntityType.proceeding, re.compile(r"\b\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4}\b")),
    (EntityType.protocol, re.compile(r"\b(?:PROTOCOLO|PROCESSO|SEI|IP|BO)\s*(?:N[ºO.]*)?\s*[:\-]?\s*[\w./-]{5,}\b", re.I)),
    (EntityType.bank_branch, re.compile(r"\bAG(?:ENCIA|\.)?\s*[:\-]?\s*\d{3,5}(?:-\d)?\b", re.I)),
    (EntityType.bank_account, re.compile(r"\b(?:CONTA|C/C|CC)\s*[:\-]?\s*\d{3,12}(?:-\d)?\b", re.I)),
    (EntityType.functional_id, re.compile(r"\bMATR[IÍ]CULA\s*(?:FUNCIONAL)?\s*[:\-]?\s*\d{3,12}\b", re.I)),
    (EntityType.rg, re.compile(r"\bRG\s*[:\-]?\s*[\d.xX-]{5,14}\b", re.I)),
    (EntityType.cnh, re.compile(r"\bCNH\s*[:\-]?\s*\d{9,11}\b", re.I)),
    (EntityType.passport, re.compile(r"\bPASSAPORTE\s*[:\-]?\s*[A-Z0-9]{6,12}\b", re.I)),
    (EntityType.pis_nis, re.compile(r"\b(?:PIS|NIS)\s*[:\-]?\s*\d{3}\.?\d{5}\.?\d{2}-?\d\b", re.I)),
]

PERSON_HINT = re.compile(
    r"\b(?:INVESTIGADO|V[IÍ]TIMA|TESTEMUNHA|DELEGADO|PROMOTOR|JUIZ|ADVOGADO|POLICIAL)\s*[:\-]\s*([A-ZÁÉÍÓÚÂÊÔÃÕÇ][A-Za-zÁÉÍÓÚÂÊÔÃÕÇ'\-]+(?:\s+[A-ZÁÉÍÓÚÂÊÔÃÕÇ][A-Za-zÁÉÍÓÚÂÊÔÃÕÇ'\-]+){1,5})",
    re.I,
)

COMPANY_HINT = re.compile(
    r"\b([A-ZÁÉÍÓÚÂÊÔÃÕÇ0-9][A-ZÁÉÍÓÚÂÊÔÃÕÇ0-9\s&.-]{3,80}\s(?:LTDA|S/A|SA|ME|EPP|EIRELI))\b",
    re.I,
)

ADDRESS_HINT = re.compile(
    r"\b(?:residente|domiciliad[oa]|situad[oa]|localizad[oa])\s+(?:na|no|à|ao|em)\s+([^,\n;]+(?:,\s*(?:n[ºo.]?\s*)?\d+[A-Za-z0-9\-]*)?)",
    re.I,
)

NAME_BEFORE_DOCUMENT = re.compile(
    r"\b([A-ZÁÉÍÓÚÂÊÔÃÕÇ][A-Za-zÁÉÍÓÚÂÊÔÃÕÇ'\-]+(?:\s+(?:da|de|do|das|dos|e)\s+|\s+)[A-ZÁÉÍÓÚÂÊÔÃÕÇ][A-Za-zÁÉÍÓÚÂÊÔÃÕÇ'\-]+(?:\s+[A-ZÁÉÍÓÚÂÊÔÃÕÇ][A-Za-zÁÉÍÓÚÂÊÔÃÕÇ'\-]+){0,4})\s*,?\s+(?:CPF|RG|CNH|PASSAPORTE)\b",
    re.I,
)

NAME_AFTER_TRANSACTION = re.compile(
    r"\b(?:para|em favor de|benefici[áa]ri[oa])\s+([A-ZÁÉÍÓÚÂÊÔÃÕÇ][A-Za-zÁÉÍÓÚÂÊÔÃÕÇ'\-]+(?:\s+(?:da|de|do|das|dos|e)\s+|\s+)[A-ZÁÉÍÓÚÂÊÔÃÕÇ][A-Za-zÁÉÍÓÚÂÊÔÃÕÇ'\-]+(?:\s+(?!(?:CPF|RG|CNH|PASSAPORTE|PIX|TED|DOC)\b)[A-ZÁÉÍÓÚÂÊÔÃÕÇ][A-Za-zÁÉÍÓÚÂÊÔÃÕÇ'\-]+){0,4})(?=\s*,|\s+(?:CPF|RG|CNH|PASSAPORTE|no valor)\b|\.|;|$)",
    re.I,
)

TRANSACTION_FRAGMENT_BLOCKLIST = ("transferência", "transferencia", " pix", " ted", " doc", "realizou", "pagamento")


def detect_entities_by_regex(text: str, document_kind: DocumentKind = DocumentKind.auto) -> list[Entity]:
    entities: list[Entity] = []
    if document_kind == DocumentKind.rif:
        entities.extend(_detect_rif_csv_entities(text))

    for entity_type, pattern in [*PATTERNS, *profile_regex_patterns(document_kind)]:
        for match in pattern.finditer(text):
            entities.append(
                Entity(
                    type=entity_type,
                    text=match.group(0),
                    start=match.start(),
                    end=match.end(),
                    source="regex",
                )
            )

    for match in PERSON_HINT.finditer(text):
        start, end = match.span(1)
        entities.append(Entity(type=EntityType.person, text=match.group(1), start=start, end=end, source="regex"))

    for pattern in (NAME_BEFORE_DOCUMENT, NAME_AFTER_TRANSACTION):
        for match in pattern.finditer(text):
            start, end = match.span(1)
            fragment = match.group(1).strip()
            if fragment.lower().startswith(("rua ", "avenida ", "av ", "travessa ", "estrada ")):
                continue
            if any(term in f" {fragment.lower()} " for term in TRANSACTION_FRAGMENT_BLOCKLIST):
                continue
            entities.append(Entity(type=EntityType.person, text=fragment, start=start, end=end, source="regex"))

    for match in ADDRESS_HINT.finditer(text):
        start, end = match.span(1)
        entities.append(Entity(type=EntityType.address, text=match.group(1), start=start, end=end, source="regex"))

    for match in COMPANY_HINT.finditer(text):
        entities.append(
            Entity(
                type=EntityType.organization,
                text=match.group(1),
                start=match.start(1),
                end=match.end(1),
                source="regex",
            )
        )

    return _deduplicate(entities)


RIF_CSV_COLUMN_TYPES = {
    "idcomunicacao": EntityType.protocol,
    "idocorrencia": EntityType.protocol,
    "numeroocorrenciabc": EntityType.protocol,
    "cpfcnpjcomunicante": EntityType.other_identifier,
    "cpfcnpjenvolvido": EntityType.other_identifier,
    "nomecomunicante": EntityType.organization,
    "nomeenvolvido": EntityType.person,
    "nomeagencia": EntityType.bank_branch,
    "numeroagencia": EntityType.bank_branch,
    "agenciaenvolvido": EntityType.bank_branch,
    "contaenvolvido": EntityType.bank_account,
}


def _detect_rif_csv_entities(text: str) -> list[Entity]:
    lines = text.splitlines(keepends=True)
    if len(lines) < 2:
        return []

    entities: list[Entity] = []
    offset = 0
    for index, line in enumerate(lines[:-1]):
        delimiter = ";" if line.count(";") >= line.count(",") and ";" in line else "," if "," in line else None
        if delimiter is None:
            offset += len(line)
            continue

        headers = [cell.strip().strip('"').lower() for cell in line.rstrip("\r\n").split(delimiter)]
        sensitive_columns = {
            column_index: RIF_CSV_COLUMN_TYPES[header]
            for column_index, header in enumerate(headers)
            if header in RIF_CSV_COLUMN_TYPES
        }
        if not sensitive_columns:
            offset += len(line)
            continue

        row_offset = offset + len(line)
        for row in lines[index + 1 :]:
            if delimiter not in row:
                break
            cells = row.rstrip("\r\n").split(delimiter)
            positions = _cell_positions(row, delimiter)
            for column_index, entity_type in sensitive_columns.items():
                if column_index >= len(cells) or column_index >= len(positions):
                    continue
                value = cells[column_index].strip().strip('"')
                if not _is_sensitive_rif_cell(value):
                    continue
                start = row_offset + positions[column_index] + cells[column_index].find(cells[column_index].strip())
                end = start + len(cells[column_index].strip())
                entities.append(Entity(type=_refine_rif_cell_type(entity_type, value), text=text[start:end], start=start, end=end, source="regex"))
            row_offset += len(row)
        break

        offset += len(line)

    return entities


def _cell_positions(row: str, delimiter: str) -> list[int]:
    positions = []
    cursor = 0
    for cell in row.rstrip("\r\n").split(delimiter):
        positions.append(cursor)
        cursor += len(cell) + len(delimiter)
    return positions


def _is_sensitive_rif_cell(value: str) -> bool:
    cleaned = value.strip()
    if not cleaned or cleaned in {"-", "0"}:
        return False
    return bool(re.search(r"[A-Za-zÀ-ÿ0-9]", cleaned))


def _refine_rif_cell_type(entity_type: EntityType, value: str) -> EntityType:
    digits = re.sub(r"\D", "", value)
    if entity_type == EntityType.other_identifier and len(digits) == 11:
        return EntityType.cpf
    if entity_type == EntityType.other_identifier and len(digits) == 14:
        return EntityType.cnpj
    return entity_type


def _deduplicate(entities: list[Entity]) -> list[Entity]:
    seen: set[tuple[int, int, str]] = set()
    unique: list[Entity] = []
    for entity in sorted(entities, key=lambda item: (item.start, -(item.end - item.start))):
        key = (entity.start, entity.end, entity.type.value)
        if key in seen:
            continue
        if any(entity.start >= other.start and entity.end <= other.end for other in unique):
            continue
        seen.add(key)
        unique.append(entity)
    return unique
