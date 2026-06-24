import re

from app.models.schemas import DocumentKind, Entity, EntityType
from app.pipeline.profile_strategy import profile_regex_patterns


NAME_CHARS = r"A-ZÀ-ÖØ-Ý"
WORD_CHARS = r"A-Za-zÀ-ÖØ-öø-ÿ"

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
    (EntityType.protocol, re.compile(r"\b(?:PROTOCOLO|PROCESSO|SEI|IP|BO)\s*(?:N[O.]*)?\s*[:\-]?\s*[\w./-]{5,}\b", re.I)),
    (EntityType.bank_branch, re.compile(r"\bAG(?:ENCIA|\.)?\s*[:\-]?\s*\d{3,5}(?:-\d)?\b", re.I)),
    (EntityType.bank_account, re.compile(r"\b(?:CONTA|C/C|CC)\s*[:\-]?\s*\d{3,12}(?:-\d)?\b", re.I)),
    (EntityType.functional_id, re.compile(r"\bMATRICULA\s*(?:FUNCIONAL)?\s*[:\-]?\s*\d{3,12}\b", re.I)),
    (EntityType.rg, re.compile(r"\bRG\s*[:\-]?\s*[\d.xX-]{5,14}\b", re.I)),
    (EntityType.cnh, re.compile(r"\bCNH\s*[:\-]?\s*\d{9,11}\b", re.I)),
    (EntityType.passport, re.compile(r"\bPASSAPORTE\s*[:\-]?\s*[A-Z0-9]{6,12}\b", re.I)),
    (EntityType.pis_nis, re.compile(r"\b(?:PIS|NIS)\s*[:\-]?\s*\d{3}\.?\d{5}\.?\d{2}-?\d\b", re.I)),
]

PERSON_HINT = re.compile(
    rf"\b(?:INVESTIGADO|VITIMA|TESTEMUNHA|DELEGADO|PROMOTOR|JUIZ|ADVOGADO|POLICIAL)\s*[:\-]\s*([{NAME_CHARS}][{WORD_CHARS}'\-]+(?:\s+[{NAME_CHARS}][{WORD_CHARS}'\-]+){{1,5}})",
    re.I,
)
COMPANY_HINT = re.compile(rf"\b([{NAME_CHARS}0-9][{NAME_CHARS}0-9\s&.-]{{3,80}}\s(?:LTDA|S/A|SA|ME|EPP|EIRELI))\b", re.I)
ADDRESS_HINT = re.compile(r"\b(?:residente|domiciliad[oa]|situad[oa]|localizad[oa])\s+(?:na|no|a|ao|em)\s+([^,\n;]+(?:,\s*(?:n[o.]?\s*)?\d+[A-Za-z0-9\-]*)?)", re.I)
NAME_BEFORE_DOCUMENT = re.compile(
    rf"\b([{NAME_CHARS}][{WORD_CHARS}'\-]+(?:\s+(?:da|de|do|das|dos|e)\s+|\s+)[{NAME_CHARS}][{WORD_CHARS}'\-]+(?:\s+[{NAME_CHARS}][{WORD_CHARS}'\-]+){{0,4}})\s*,?\s+(?:CPF|RG|CNH|PASSAPORTE)\b",
    re.I,
)
NAME_AFTER_TRANSACTION = re.compile(
    rf"\b(?:para|em favor de|beneficiari[oa])\s+([{NAME_CHARS}][{WORD_CHARS}'\-]+(?:\s+(?:da|de|do|das|dos|e)\s+|\s+)[{NAME_CHARS}][{WORD_CHARS}'\-]+(?:\s+(?!(?:CPF|RG|CNH|PASSAPORTE|PIX|TED|DOC)\b)[{NAME_CHARS}][{WORD_CHARS}'\-]+){{0,4}})(?=\s*,|\s+(?:CPF|RG|CNH|PASSAPORTE|no valor)\b|\.|;|$)",
    re.I,
)
TRANSACTION_FRAGMENT_BLOCKLIST = ("transferencia", " pix", " ted", " doc", "realizou", "pagamento")


def detect_entities_by_regex(text: str, document_kind: DocumentKind) -> list[Entity]:
    entities: list[Entity] = []
    if document_kind == DocumentKind.rif:
        entities.extend(_detect_rif_csv_entities(text))
    if document_kind == DocumentKind.extrato_bancario:
        entities.extend(_detect_bank_statement_entities(text))

    for entity_type, pattern in [*PATTERNS, *profile_regex_patterns(document_kind)]:
        for match in pattern.finditer(text):
            entities.append(Entity(type=entity_type, text=match.group(0), start=match.start(), end=match.end(), source="regex"))

    for match in PERSON_HINT.finditer(text):
        entities.append(Entity(type=EntityType.person, text=match.group(1), start=match.start(1), end=match.end(1), source="regex"))

    for pattern in (NAME_BEFORE_DOCUMENT, NAME_AFTER_TRANSACTION):
        for match in pattern.finditer(text):
            fragment = match.group(1).strip()
            if fragment.lower().startswith(("rua ", "avenida ", "av ", "travessa ", "estrada ")):
                continue
            if any(term in f" {fragment.lower()} " for term in TRANSACTION_FRAGMENT_BLOCKLIST):
                continue
            entities.append(Entity(type=EntityType.person, text=fragment, start=match.start(1), end=match.end(1), source="regex"))

    for match in ADDRESS_HINT.finditer(text):
        entities.append(Entity(type=EntityType.address, text=match.group(1), start=match.start(1), end=match.end(1), source="regex"))

    for match in COMPANY_HINT.finditer(text):
        entities.append(Entity(type=EntityType.organization, text=match.group(1), start=match.start(1), end=match.end(1), source="regex"))

    return _deduplicate(entities)


BANK_STATEMENT_TITULAR = re.compile(rf"\bTitular\s*:\s*([{NAME_CHARS}][{NAME_CHARS} '\.-]{{5,120}}?)(?=\s*\()", re.I)
BANK_STATEMENT_HEADER_ID = re.compile(r"\bCPF/CNPJ\s*:\s*(\d{5,14})\b", re.I)
BANK_STATEMENT_DETAILED_COUNTERPARTY = re.compile(
    rf"\b[CD]\s+(\d{{5,14}})\s+([{NAME_CHARS}][{NAME_CHARS}0-9 '&\.-]{{4,120}}?)(?=\s+(?:\d+\s+){{0,3}}(?:SAQUE|TARIFA|TRANSFER|CONTRAPARTIDA|PAGAMENTO|PIX|TED|DOC|$))",
    re.I,
)
BANK_STATEMENT_CONSOLIDATED_COUNTERPARTY = re.compile(
    rf"^\s*([{NAME_CHARS}][{NAME_CHARS}0-9 '&\.-]{{4,120}}?)\s+(\d{{5,14}})\s+(?:\d+\s+){{1,4}}(?:Conta\s+(?:Corrente|Poupanca)|R\$)",
    re.I | re.M,
)
BANK_STATEMENT_AUTHORIZED_BY_NAME = re.compile(rf"\bPOR\s+([{NAME_CHARS}][{NAME_CHARS} '\.-]{{6,100}})(?=\s|$)", re.I)


def _detect_bank_statement_entities(text: str) -> list[Entity]:
    entities: list[Entity] = []

    for match in BANK_STATEMENT_TITULAR.finditer(text):
        titular = match.group(1).strip()
        entities.append(Entity(type=EntityType.person, text=match.group(1), start=match.start(1), end=match.end(1), source="regex"))
        surname_variant = _bank_statement_surname_variant(titular)
        if surname_variant:
            entities.extend(_find_literal_person_entities(text, surname_variant))

    for match in BANK_STATEMENT_HEADER_ID.finditer(text):
        entities.append(_typed_identifier_entity(text, match.start(1), match.end(1)))

    for match in BANK_STATEMENT_DETAILED_COUNTERPARTY.finditer(text):
        entities.append(_typed_identifier_entity(text, match.start(1), match.end(1)))
        name = match.group(2).strip()
        if _looks_like_bank_statement_counterparty(name):
            entities.append(Entity(type=_bank_counterparty_type(name), text=match.group(2), start=match.start(2), end=match.end(2), source="regex"))

    for match in BANK_STATEMENT_CONSOLIDATED_COUNTERPARTY.finditer(text):
        name = match.group(1).strip()
        if _looks_like_bank_statement_counterparty(name):
            entities.append(Entity(type=_bank_counterparty_type(name), text=match.group(1), start=match.start(1), end=match.end(1), source="regex"))
        entities.append(_typed_identifier_entity(text, match.start(2), match.end(2)))

    for match in BANK_STATEMENT_AUTHORIZED_BY_NAME.finditer(text):
        fragment = match.group(1).strip()
        if _looks_like_bank_statement_counterparty(fragment):
            entities.append(Entity(type=EntityType.person, text=match.group(1), start=match.start(1), end=match.end(1), source="regex"))

    return entities


def _typed_identifier_entity(text: str, start: int, end: int) -> Entity:
    value = text[start:end]
    digits = re.sub(r"\D", "", value)
    if 9 <= len(digits) <= 11:
        entity_type = EntityType.cpf
    elif len(digits) == 14:
        entity_type = EntityType.cnpj
    else:
        entity_type = EntityType.other_identifier
    return Entity(type=entity_type, text=value, start=start, end=end, source="regex")


def _bank_statement_surname_variant(name: str) -> str | None:
    parts = [part for part in re.split(r"\s+", name.strip()) if len(part) > 1]
    if len(parts) < 4:
        return None
    return " ".join(parts[-3:])


def _find_literal_person_entities(text: str, value: str) -> list[Entity]:
    pattern = re.compile(rf"(?<!\w){re.escape(value)}(?!\w)", re.I)
    return [Entity(type=EntityType.person, text=match.group(0), start=match.start(), end=match.end(), source="regex") for match in pattern.finditer(text)]


def _looks_like_bank_statement_counterparty(value: str) -> bool:
    normalized = value.strip().upper()
    if not normalized or normalized in {"BANCO DO BRASIL S.A.", "BCO DO BRASIL S.A.", "CAIXA ECONOMICA FEDERAL"}:
        return False
    protected_terms = ("SAQUE", "TARIFA", "RESGATE", "APLICACAO", "TRANSFERENCIA", "COMPRA COM CARTAO", "JUROS")
    return not any(term in normalized for term in protected_terms)


def _bank_counterparty_type(value: str) -> EntityType:
    normalized = value.upper()
    company_terms = (" LTDA", " S/A", " S.A.", " EIRELI", " INDUSTRIA", " COMERCIO", " MINISTERIO", " CCLA ")
    return EntityType.organization if any(term in normalized for term in company_terms) else EntityType.person


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

    offset = 0
    for index, line in enumerate(lines[:-1]):
        delimiter = ";" if line.count(";") >= line.count(",") and ";" in line else "," if "," in line else None
        if delimiter is None:
            offset += len(line)
            continue

        headers = [cell.strip().strip('"').lower() for cell in line.rstrip("\r\n").split(delimiter)]
        sensitive_columns = {column_index: RIF_CSV_COLUMN_TYPES[header] for column_index, header in enumerate(headers) if header in RIF_CSV_COLUMN_TYPES}
        if not sensitive_columns:
            offset += len(line)
            continue

        return _detect_rif_rows(text, lines[index + 1 :], offset + len(line), delimiter, sensitive_columns)

    return []


def _detect_rif_rows(
    text: str,
    rows: list[str],
    row_offset: int,
    delimiter: str,
    sensitive_columns: dict[int, EntityType],
) -> list[Entity]:
    entities: list[Entity] = []
    for row in rows:
        if delimiter not in row:
            break
        cells = row.rstrip("\r\n").split(delimiter)
        positions = _cell_positions(row, delimiter)
        for column_index, entity_type in sensitive_columns.items():
            if column_index >= len(cells) or column_index >= len(positions):
                continue
            raw_cell = cells[column_index]
            value = raw_cell.strip().strip('"')
            if not _is_sensitive_rif_cell(value):
                continue
            start = row_offset + positions[column_index] + raw_cell.find(raw_cell.strip())
            end = start + len(raw_cell.strip())
            entities.append(Entity(type=_refine_rif_cell_type(entity_type, value), text=text[start:end], start=start, end=end, source="regex"))
        row_offset += len(row)
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
