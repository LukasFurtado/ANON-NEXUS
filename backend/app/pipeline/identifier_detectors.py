import re
import unicodedata
from dataclasses import dataclass

from app.models.schemas import Entity, EntityType
from app.services.institutional_library import is_institutional_retention
from app.services.name_library import first_names, name_particles, surnames


VALID_DDDS = {
    11, 12, 13, 14, 15, 16, 17, 18, 19,
    21, 22, 24, 27, 28,
    31, 32, 33, 34, 35, 37, 38,
    41, 42, 43, 44, 45, 46, 47, 48, 49,
    51, 53, 54, 55,
    61, 62, 63, 64, 65, 66, 67, 68, 69,
    71, 73, 74, 75, 77, 79,
    81, 82, 83, 84, 85, 86, 87, 88, 89,
    91, 92, 93, 94, 95, 96, 97, 98, 99,
}


COMMON_FIRST_NAMES = {
    "aline", "ana", "andre", "antonio", "bruna", "carlos", "claudia", "daniel",
    "eduardo", "fernanda", "francinete", "gorete", "joao", "jose", "juliana",
    "luiz", "luis", "maria", "marcos", "mariana", "paulo", "pedro", "rafael",
    "renata", "roberto", "sandra", "silvia", "thiago", "vanessa",
}


COMMON_SURNAMES = {
    "almeida", "alves", "araujo", "barbosa", "barros", "bezerra", "cavalcanti",
    "costa", "ferreira", "gomes", "lima", "medeiros", "melo", "nascimento",
    "nunes", "oliveira", "pereira", "rocha", "santos", "silva", "siqueira",
    "souza", "sousa", "teixeira", "vieira",
}


INSTITUTIONAL_TERMS = {
    "banco central", "bacen", "coaf", "receita federal", "policia civil",
    "policia federal", "pcpe", "ministerio publico", "ministerio publico federal",
    "tribunal de justica", "supremo tribunal federal", "superior tribunal de justica",
    "prefeitura", "camara municipal", "fundo municipal", "caixa economica federal",
    "banco do brasil", "bradesco", "santander", "itau", "nubank", "sicredi",
    "sicoob", "loterias", "loteca", "correios", "petrobras",
}


CPF_PATTERNS = [
    re.compile(r"(?<!\d)0?\d{3}\.?\d{3}\.?\d{3}-?\d{2}(?!\d)"),
    re.compile(r"(?<!\d)\d{3}\s\d{3}\s\d{3}\s\d{2}(?!\d)"),
    re.compile(r"(?<!\d)\d{3}-\d{3}-\d{3}-\d{2}(?!\d)"),
]

TRUNCATED_CPF_PATTERN = re.compile(r"(?<!\d)\d{10}(?!\d)")
CPF_CONTEXT_PATTERN = re.compile(r"\b(?:CPF|CPF/CNPJ|CPFCNPJ|cpfCnpj\w*)\b", re.I)

CNPJ_PATTERNS = [
    re.compile(r"(?<!\d)\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}(?!\d)"),
    re.compile(r"(?<!\d)\d{2}\s\d{3}\s\d{3}\s\d{4}\s\d{2}(?!\d)"),
]

PHONE_PATTERNS = [
    re.compile(r"(?<!\d)(?:\+55\s?)?\(?\d{2}\)?\s?9\d{4}-?\d{4}(?!\d)"),
    re.compile(r"(?<!\d)(?:\+55\s?)?\(?\d{2}\)?\s?[2-9]\d{3}-?\d{4}(?!\d)"),
]

BANK_BRANCH_PATTERN = re.compile(r"\b(?:AG(?:ENCIA|\.)?)\s*[:\-]?\s*(\d{4,5})(?:[-/][0-9X])?\b", re.I)
BANK_ACCOUNT_PATTERN = re.compile(r"\b(?:CONTA|C/C|CC|CTA\.?)\s*[:\-]?\s*(\d{5,14})(?:[-/][0-9X])?\b", re.I)
BANK_COMBINED_PATTERN = re.compile(
    r"\b(?:BANCO|BCO)\s*[:\-]?\s*\d{3}.*?\bAG(?:ENCIA|\.)?\s*[:\-]?\s*\d{4,5}.*?\b(?:CONTA|C/C|CC)\s*[:\-]?\s*\d{5,14}(?:[-/][0-9X])?",
    re.I,
)

NAME_CONTEXT_PATTERN = re.compile(
    r"\b(?:vitima|investigad[oa]|testemunha|acusad[oa]|autor[ae]?|beneficiari[oa]|titular|remetente|depositante|favorecid[oa])\s+([A-ZÀ-ÖØ-Ý][A-Za-zÀ-ÖØ-öø-ÿ'\.-]+(?:\s+(?:de|da|do|das|dos|e)\s+|\s+)[A-ZÀ-ÖØ-Ý][A-Za-zÀ-ÖØ-öø-ÿ'\.-]+(?:\s+[A-ZÀ-ÖØ-Ý][A-Za-zÀ-ÖØ-öø-ÿ'\.-]+){0,4})",
    re.I,
)
KNOWN_NAME_PATTERN = re.compile(
    r"\b([A-ZÀ-ÖØ-Ý][A-Za-zÀ-ÖØ-öø-ÿ'\.-]+(?:\s+(?:de|da|do|das|dos|e)\s+|\s+)[A-ZÀ-ÖØ-Ý][A-Za-zÀ-ÖØ-öø-ÿ'\.-]+(?:\s+[A-ZÀ-ÖØ-Ý][A-Za-zÀ-ÖØ-öø-ÿ'\.-]+){0,4})\b"
)


@dataclass(frozen=True)
class DetectionDecision:
    text: str
    entity_type: EntityType
    start: int
    end: int
    confidence: float
    detector: str


def detect_structured_identifiers(text: str) -> list[Entity]:
    decisions: list[DetectionDecision] = []
    decisions.extend(_detect_cpfs(text))
    decisions.extend(_detect_cnpjs(text))
    decisions.extend(_detect_phones(text))
    decisions.extend(_detect_bank_data(text))
    decisions.extend(_detect_brazilian_names(text))
    return [
        Entity(type=item.entity_type, text=item.text, start=item.start, end=item.end, source=f"detector:{item.detector}")
        for item in _dedupe_decisions(decisions)
    ]


def is_protected_institution(value: str) -> bool:
    normalized = normalize_text(value)
    return is_institutional_retention(value) or any(term in normalized for term in INSTITUTIONAL_TERMS)


def is_valid_cpf_digits(value: str) -> bool:
    digits = _digits(value)
    if len(digits) == 12 and digits.startswith("0"):
        digits = digits[1:]
    if len(digits) == 10 and is_possible_truncated_cpf_digits(digits):
        return True
    if len(digits) != 11 or digits == digits[0] * 11:
        return False
    first = _cpf_digit(digits[:9], 10)
    second = _cpf_digit(digits[:9] + str(first), 11)
    return digits[-2:] == f"{first}{second}"


def is_possible_truncated_cpf_digits(value: str) -> bool:
    digits = _digits(value)
    if len(digits) != 10:
        return False
    restored = f"0{digits}"
    if restored == restored[0] * 11:
        return False
    first = _cpf_digit(restored[:9], 10)
    second = _cpf_digit(restored[:9] + str(first), 11)
    return restored[-2:] == f"{first}{second}"


def is_valid_cnpj_digits(value: str) -> bool:
    digits = _digits(value)
    if len(digits) != 14 or digits == digits[0] * 14:
        return False
    first = _cnpj_digit(digits[:12], [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2])
    second = _cnpj_digit(digits[:12] + str(first), [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2])
    return digits[-2:] == f"{first}{second}"


def normalize_text(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value or "")
    no_accent = "".join(char for char in decomposed if not unicodedata.combining(char))
    return re.sub(r"\s+", " ", no_accent.lower()).strip()


def _detect_cpfs(text: str) -> list[DetectionDecision]:
    items: list[DetectionDecision] = []
    for pattern in CPF_PATTERNS:
        for match in pattern.finditer(text):
            if is_valid_cpf_digits(match.group(0)):
                items.append(DetectionDecision(match.group(0), EntityType.cpf, match.start(), match.end(), 0.98, "cpf"))
    items.extend(_detect_truncated_cpfs(text))
    return items


def _detect_truncated_cpfs(text: str) -> list[DetectionDecision]:
    items: list[DetectionDecision] = []
    line_start = 0
    for line in text.splitlines(keepends=True):
        line_text = line.rstrip("\r\n")
        valid_cpf_in_line = any(is_valid_cpf_digits(match.group(0)) and len(_digits(match.group(0))) == 11 for pattern in CPF_PATTERNS for match in pattern.finditer(line_text))
        has_cpf_context = bool(CPF_CONTEXT_PATTERN.search(line_text))
        if has_cpf_context or valid_cpf_in_line:
            for match in TRUNCATED_CPF_PATTERN.finditer(line_text):
                value = match.group(0)
                if is_possible_truncated_cpf_digits(value):
                    items.append(
                        DetectionDecision(
                            value,
                            EntityType.cpf,
                            line_start + match.start(),
                            line_start + match.end(),
                            0.9 if has_cpf_context else 0.82,
                            "cpf_zero_inicial_ausente",
                        )
                    )
        line_start += len(line)
    return items


def _detect_cnpjs(text: str) -> list[DetectionDecision]:
    items: list[DetectionDecision] = []
    for pattern in CNPJ_PATTERNS:
        for match in pattern.finditer(text):
            if is_valid_cnpj_digits(match.group(0)):
                items.append(DetectionDecision(match.group(0), EntityType.cnpj, match.start(), match.end(), 0.98, "cnpj"))
    return items


def _detect_phones(text: str) -> list[DetectionDecision]:
    items: list[DetectionDecision] = []
    for pattern in PHONE_PATTERNS:
        for match in pattern.finditer(text):
            if _valid_phone(match.group(0)):
                items.append(DetectionDecision(match.group(0), EntityType.phone, match.start(), match.end(), 0.92, "telefone"))
    return items


def _detect_bank_data(text: str) -> list[DetectionDecision]:
    items: list[DetectionDecision] = []
    for match in BANK_COMBINED_PATTERN.finditer(text):
        items.append(DetectionDecision(match.group(0), EntityType.bank_account, match.start(), match.end(), 0.9, "bancario_completo"))
    for pattern, entity_type, detector in (
        (BANK_BRANCH_PATTERN, EntityType.bank_branch, "agencia"),
        (BANK_ACCOUNT_PATTERN, EntityType.bank_account, "conta"),
    ):
        for match in pattern.finditer(text):
            items.append(DetectionDecision(match.group(0), entity_type, match.start(), match.end(), 0.88, detector))
    return items


def _detect_brazilian_names(text: str) -> list[DetectionDecision]:
    items: list[DetectionDecision] = []
    for pattern, confidence in ((NAME_CONTEXT_PATTERN, 0.94), (KNOWN_NAME_PATTERN, 0.86)):
        for match in pattern.finditer(text):
            name = _trim_person_name(match.group(1).strip())
            if _looks_like_brazilian_person_name(name):
                offset = match.group(1).find(name)
                start = match.start(1) + max(offset, 0)
                items.append(DetectionDecision(name, EntityType.person, start, start + len(name), confidence, "nomes"))
    return items


def _trim_person_name(value: str) -> str:
    raw_tokens = re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿ'\.-]+", value)
    accepted: list[str] = []
    library_first_names = COMMON_FIRST_NAMES | first_names()
    library_surnames = COMMON_SURNAMES | surnames()
    particles = name_particles()
    for token in raw_tokens:
        normalized = normalize_text(token)
        if normalized in {"cpf", "cnpj", "rg", "cnh", "passaporte"}:
            break
        if not accepted:
            if normalized not in library_first_names:
                continue
            accepted.append(token)
            continue
        if normalized in particles or normalized in library_surnames or normalized in library_first_names:
            accepted.append(token)
            continue
        break
    return " ".join(accepted)


def _looks_like_brazilian_person_name(name: str) -> bool:
    if is_protected_institution(name):
        return False
    tokens = [normalize_text(token) for token in re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿ'\.-]+", name)]
    library_first_names = COMMON_FIRST_NAMES | first_names()
    library_surnames = COMMON_SURNAMES | surnames()
    tokens = [token for token in tokens if token not in name_particles()]
    if len(tokens) < 2 or len(tokens) > 7:
        return False
    has_first = tokens[0] in library_first_names
    has_surname = any(token in library_surnames for token in tokens[1:])
    return has_first and has_surname


def _valid_phone(value: str) -> bool:
    digits = _digits(value)
    if digits.startswith("55") and len(digits) in {12, 13}:
        digits = digits[2:]
    if len(digits) not in {10, 11}:
        return False
    ddd = int(digits[:2])
    if ddd not in VALID_DDDS:
        return False
    first = int(digits[2])
    if len(digits) == 11:
        return first == 9
    return 2 <= first <= 9


def _cpf_digit(base: str, weight_start: int) -> int:
    total = sum(int(digit) * (weight_start - index) for index, digit in enumerate(base))
    result = 11 - (total % 11)
    return 0 if result >= 10 else result


def _cnpj_digit(base: str, weights: list[int]) -> int:
    total = sum(int(digit) * weight for digit, weight in zip(base, weights, strict=True))
    result = 11 - (total % 11)
    return 0 if result >= 10 else result


def _digits(value: str) -> str:
    return re.sub(r"\D", "", value or "")


def _dedupe_decisions(items: list[DetectionDecision]) -> list[DetectionDecision]:
    result: list[DetectionDecision] = []
    for item in sorted(items, key=lambda part: (part.start, -(part.end - part.start), -part.confidence)):
        if any(item.start >= existing.start and item.end <= existing.end for existing in result):
            continue
        result.append(item)
    return result
