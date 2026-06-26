import re

from app.models.schemas import DocumentKind, Entity, EntityType
from app.pipeline.identifier_detectors import detect_structured_identifiers, is_valid_cnpj_digits, is_valid_cpf_digits
from app.pipeline.profile_strategy import profile_regex_patterns
from app.pipeline.rif_rules import detect_rif_csv_subtype, normalize_rif_header, rif_column_types_for_headers


NAME_CHARS = r"A-ZÀ-ÖØ-Ý"
WORD_CHARS = r"A-Za-zÀ-ÖØ-öø-ÿ"

PATTERNS: list[tuple[EntityType, re.Pattern[str]]] = [
    (EntityType.email, re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)),
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
    (EntityType.functional_id, re.compile(r"\bMATRICULA\s*(?:FUNCIONAL)?\s*[:\-]?\s*\d{3,12}\b", re.I)),
    (EntityType.rg, re.compile(r"\bRG\s*[:\-]?\s*[\d.xX-]{5,14}\b", re.I)),
    (EntityType.cnh, re.compile(r"\bCNH\s*[:\-]?\s*\d{9,11}\b", re.I)),
    (EntityType.passport, re.compile(r"\bPASSAPORTE\s*[:\-]?\s*[A-Z0-9]{6,12}\b", re.I)),
    (EntityType.pis_nis, re.compile(r"\b(?:PIS|NIS)\s*[:\-]?\s*\d{3}\.?\d{5}\.?\d{2}-?\d\b", re.I)),
]

RIF_SUSPECT_COMPANY_CONTEXT = re.compile(
    rf"\b(?:empresa|envolvid[ao]|titular|favorecid[ao]|beneficiari[ao]|comunicante)\s*[:\-]?\s*([{NAME_CHARS}0-9][{WORD_CHARS}0-9 '&\.-]{{4,90}}?(?:LTDA|S/A|S\.A\.|ME|EPP|EIRELI)?)\b",
    re.I,
)
PIX_EMAIL_HINT = re.compile(r"\b(?:PIX|CHAVE PIX|CHAVE)\s*[:\-]?\s*([A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,})\b", re.I)

PERSON_HINT = re.compile(
    rf"\b(?:INVESTIGADO|VITIMA|TESTEMUNHA|DELEGADO|PROMOTOR|JUIZ|ADVOGADO|POLICIAL)\s*[:\-]\s*([{NAME_CHARS}][{WORD_CHARS}'\-]+(?:\s+[{NAME_CHARS}][{WORD_CHARS}'\-]+){{1,5}})",
    re.I,
)
COMPANY_SUFFIX_PATTERN = (
    r"(?:LTDA|L\.T\.D\.A\.|ME|M\.E\.|S/A|S\.A\.|SA|CIA\.?|COMPANHIA|EPP|EIRELI|EI|SLU|SCP|SPE|S/S|SS|"
    r"ASSOCIACAO|ASSOCIAÇÃO|COOPERATIVA|COOP)"
)
COMPANY_HINT = re.compile(
    rf"\b([{NAME_CHARS}0-9][{WORD_CHARS}0-9\s&,'/-]{{2,120}}?\s{COMPANY_SUFFIX_PATTERN})(?=\b|\s|$|[,.;:/\-\n])",
    re.I,
)
ADDRESS_HINT = re.compile(r"\b(?:residente|domiciliad[oa]|situad[oa]|localizad[oa])\s+(?:na|no|a|ao|em)\s+([^,\n;]+(?:,\s*(?:n[o.]?\s*)?\d+[A-Za-z0-9\-]*)?)", re.I)
NAME_BEFORE_DOCUMENT = re.compile(
    rf"\b([{NAME_CHARS}][{WORD_CHARS}'\-]+(?:\s+(?:da|de|do|das|dos|e)\s+|\s+)[{NAME_CHARS}][{WORD_CHARS}'\-]+(?:\s+[{NAME_CHARS}][{WORD_CHARS}'\-]+){{0,4}})\s*,?\s+(?:CPF|RG|CNH|PASSAPORTE)\b",
    re.I,
)
NAME_BEFORE_RAW_CPF = re.compile(
    rf"\b([{NAME_CHARS}][{WORD_CHARS}'\-]+(?:\s+(?:da|de|do|das|dos|e)\s+|\s+)[{NAME_CHARS}][{WORD_CHARS}'\-]+(?:\s+(?!(?:CPF|CPF/CNPJ|RG|CNH|PASSAPORTE)\b)[{NAME_CHARS}][{WORD_CHARS}'\-]+){{0,5}})\s*[-,;/]?\s*(?:CPF\s*)?(0?\d{{3}}\.?\d{{3}}\.?\d{{3}}-?\d{{2}}|\d{{10}})(?!\d)",
    re.I,
)
NAME_AFTER_TRANSACTION = re.compile(
    rf"\b(?:para|em favor de|beneficiari[oa])\s+([{NAME_CHARS}][{WORD_CHARS}'\-]+(?:\s+(?:da|de|do|das|dos|e)\s+|\s+)[{NAME_CHARS}][{WORD_CHARS}'\-]+(?:\s+(?!(?:CPF|RG|CNH|PASSAPORTE|PIX|TED|DOC)\b)[{NAME_CHARS}][{WORD_CHARS}'\-]+){{0,4}})(?=\s*,|\s+(?:CPF|RG|CNH|PASSAPORTE|no valor)\b|\.|;|$)",
    re.I,
)
TRANSACTION_FRAGMENT_BLOCKLIST = ("transferencia", " pix", " ted", " doc", "realizou", "pagamento")


def detect_entities_by_regex(text: str, document_kind: DocumentKind, original_filename: str | None = None) -> list[Entity]:
    entities: list[Entity] = detect_structured_identifiers(text)
    if document_kind == DocumentKind.rif:
        entities.extend(_detect_rif_csv_entities(text, original_filename))
        for match in RIF_SUSPECT_COMPANY_CONTEXT.finditer(text):
            fragment = match.group(1).strip()
            if len(fragment) >= 5 and not fragment.upper().startswith(("CPF", "CNPJ", "VALOR", "DATA")):
                entities.append(
                    Entity(
                        type=_bank_counterparty_type(fragment),
                        text=match.group(1),
                        start=match.start(1),
                        end=match.end(1),
                        source="regex",
                    )
                )
        for match in PIX_EMAIL_HINT.finditer(text):
            entities.append(Entity(type=EntityType.pix, text=match.group(1), start=match.start(1), end=match.end(1), source="regex"))
        entities.extend(_detect_rif_narrative_entities(text))
    if document_kind == DocumentKind.extrato_bancario:
        entities.extend(_detect_bank_statement_entities(text))

    for entity_type, pattern in [*PATTERNS, *profile_regex_patterns(document_kind)]:
        for match in pattern.finditer(text):
            entities.append(Entity(type=entity_type, text=match.group(0), start=match.start(), end=match.end(), source="regex"))

    for match in PERSON_HINT.finditer(text):
        entities.append(Entity(type=EntityType.person, text=match.group(1), start=match.start(1), end=match.end(1), source="regex"))

    for pattern in (NAME_BEFORE_DOCUMENT, NAME_AFTER_TRANSACTION):
        for match in pattern.finditer(text):
            start = match.start(1)
            fragment = match.group(1).strip()
            if document_kind == DocumentKind.rif:
                fragment, start = _clean_rif_person_fragment(match.group(1), match.start(1))
            if _is_bad_person_fragment(fragment):
                continue
            entities.append(Entity(type=EntityType.person, text=fragment, start=start, end=start + len(fragment), source="regex"))

    for match in NAME_BEFORE_RAW_CPF.finditer(text):
        start = match.start(1)
        fragment = match.group(1).strip()
        if document_kind == DocumentKind.rif:
            fragment, start = _clean_rif_person_fragment(match.group(1), match.start(1))
        if not _is_bad_person_fragment(fragment):
            entities.append(Entity(type=EntityType.person, text=fragment, start=start, end=start + len(fragment), source="regex"))
        entities.append(_typed_identifier_entity(text, match.start(2), match.end(2)))

    for match in ADDRESS_HINT.finditer(text):
        entities.append(Entity(type=EntityType.address, text=match.group(1), start=match.start(1), end=match.end(1), source="regex"))

    for match in COMPANY_HINT.finditer(text):
        fragment, start = _clean_company_fragment(match.group(1), match.start(1))
        entities.append(Entity(type=EntityType.organization, text=fragment, start=start, end=start + len(fragment), source="regex"))

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
    if len(digits) == 11 and is_valid_cpf_digits(value):
        entity_type = EntityType.cpf
    elif len(digits) == 10 and is_valid_cpf_digits(value):
        entity_type = EntityType.cpf
    elif len(digits) == 14 and is_valid_cnpj_digits(value):
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
    return EntityType.organization if _has_company_signal(value) else EntityType.person


def _has_company_signal(value: str) -> bool:
    normalized = re.sub(r"\s+", " ", value.upper()).strip()
    if re.search(rf"(?:^|\s){COMPANY_SUFFIX_PATTERN}\.?$", normalized, re.I):
        return True
    company_terms = (
        " INDUSTRIA",
        " INDÚSTRIA",
        " COMERCIO",
        " COMÉRCIO",
        " SERVICOS",
        " SERVIÇOS",
        " PARTICIPACOES",
        " PARTICIPAÇÕES",
        " MINISTERIO",
        " CCLA ",
        " COOPERATIVA",
        " ASSOCIACAO",
        " ASSOCIAÇÃO",
    )
    return any(term in f" {normalized} " for term in company_terms)


RIF_NARRATIVE_NAME_BEFORE_ID = re.compile(
    rf"\b([{NAME_CHARS}][{WORD_CHARS}'\.-]+(?:\s+(?:DA|DE|DO|DAS|DOS|E)\s+|\s+)[{NAME_CHARS}][{WORD_CHARS}'\.-]+(?:\s+[{NAME_CHARS}][{WORD_CHARS}'\.-]+){{0,5}})\s*[-,]?\s*(?:CPF|CNPJ)\b",
    re.I,
)
RIF_NARRATIVE_COMPANY_BEFORE_ID = re.compile(
    rf"\b([{NAME_CHARS}0-9][{WORD_CHARS}0-9\s&,'/-]{{3,120}}?\s{COMPANY_SUFFIX_PATTERN})\s*[-,;/]?\s*(?:CNPJ|CPF/CNPJ)?\s*\d{{5,14}}\b",
    re.I,
)
RIF_NARRATIVE_NAME_IN_PARENS_AFTER_ID = re.compile(
    rf"\b(?:CPF|CNPJ)?\s*\d{{3}}\.?\d{{3}}\.?\d{{3}}-?\d{{2}}\s*\(\s*([{NAME_CHARS}][{WORD_CHARS}'\.-]+(?:\s+[{NAME_CHARS}][{WORD_CHARS}'\.-]+){{1,6}})\s*\)",
    re.I,
)
RIF_NARRATIVE_LABEL_NAME = re.compile(
    rf"\b(?:TITULAR|REMETENTE|BENEFICIARIO|BENEFICIARIA|SACADOR|DEPOSITANTE|FAVORECIDO|FAVORECIDA)\s*[:\-]\s*([{NAME_CHARS}][{WORD_CHARS}'\.-]+(?:\s+[{NAME_CHARS}][{WORD_CHARS}'\.-]+){{1,6}})",
    re.I,
)


def _detect_rif_csv_entities(text: str, original_filename: str | None = None) -> list[Entity]:
    lines = text.splitlines(keepends=True)
    if len(lines) < 2:
        return []
    subtype = detect_rif_csv_subtype(text, original_filename)

    offset = 0
    for index, line in enumerate(lines[:-1]):
        delimiter = ";" if line.count(";") >= line.count(",") and ";" in line else "," if "," in line else None
        if delimiter is None:
            offset += len(line)
            continue

        headers = [normalize_rif_header(cell) for cell in line.rstrip("\r\n").split(delimiter)]
        sensitive_columns = rif_column_types_for_headers(headers, subtype)
        if not sensitive_columns:
            offset += len(line)
            continue

        return _detect_rif_rows(text, lines[index + 1 :], offset + len(line), delimiter, sensitive_columns)

    return []


def _detect_rif_narrative_entities(text: str) -> list[Entity]:
    entities: list[Entity] = []
    for match in RIF_NARRATIVE_COMPANY_BEFORE_ID.finditer(text):
        fragment, start = _clean_company_fragment(match.group(1), match.start(1))
        if not _is_rif_operational_fragment(fragment):
            entities.append(Entity(type=EntityType.organization, text=fragment, start=start, end=start + len(fragment), source="regex"))
    for pattern in (RIF_NARRATIVE_NAME_BEFORE_ID, RIF_NARRATIVE_NAME_IN_PARENS_AFTER_ID, RIF_NARRATIVE_LABEL_NAME):
        for match in pattern.finditer(text):
            fragment, start = _clean_rif_person_fragment(match.group(1), match.start(1))
            if _is_rif_operational_fragment(fragment):
                continue
            entities.append(Entity(type=EntityType.person, text=fragment, start=start, end=start + len(fragment), source="regex"))
    return entities


def _clean_rif_person_fragment(value: str, start: int) -> tuple[str, int]:
    fragment = re.sub(r"\s+", " ", value.strip())
    prefix = re.match(r"(?i)^.*\b(?:por|para|de)\s+", fragment)
    if prefix:
        fragment = fragment[prefix.end() :].strip()
        start = start + prefix.end()
    suffix = re.search(r"(?i)\s+(?:CPF|CNPJ|RG|CNH|PASSAPORTE)\b.*$", fragment)
    if suffix:
        fragment = fragment[: suffix.start()].strip()
    return fragment, start


def _clean_company_fragment(value: str, start: int) -> tuple[str, int]:
    fragment = re.sub(r"\s+", " ", value.strip())
    prefix = re.match(r"(?i)^(?:e|de|da|do|das|dos)\s+", fragment)
    if prefix:
        fragment = fragment[prefix.end() :].strip()
        start += prefix.end()
    return fragment, start


def _is_rif_operational_fragment(value: str) -> bool:
    normalized = re.sub(r"\s+", " ", value.upper()).strip()
    protected = (
        "BANCO",
        "BACEN",
        "COAF",
        "PIX",
        "TED",
        "DOC",
        "DEPOSITO",
        "TRANSFERENCIA",
        "SAQUE",
        "PAGAMENTO",
        "CREDITO",
        "DEBITO",
        "LOTERIAS",
    )
    return any(term in normalized for term in protected)


def _is_bad_person_fragment(fragment: str) -> bool:
    normalized = fragment.lower()
    if normalized.startswith(("rua ", "avenida ", "av ", "travessa ", "estrada ")):
        return True
    return any(term in f" {normalized} " for term in TRANSACTION_FRAGMENT_BLOCKLIST)


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
