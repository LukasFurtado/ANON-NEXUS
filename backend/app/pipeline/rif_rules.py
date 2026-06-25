import re

from app.models.schemas import EntityType


RIF_ENVOLVIDOS = "rif_envolvidos"
RIF_OCORRENCIAS = "rif_ocorrencias"
RIF_COMUNICACOES = "rif_comunicacoes"
RIF_UNKNOWN = "rif_desconhecido"


RIF_FILENAME_PATTERNS: dict[str, re.Pattern[str]] = {
    RIF_ENVOLVIDOS: re.compile(r"^RIF\d+_Envolvidos\.csv$", re.I),
    RIF_OCORRENCIAS: re.compile(r"^RIF\d+_Ocorrencias\.csv$", re.I),
    RIF_COMUNICACOES: re.compile(r"^RIF\d+_Comunicacoes\.csv$", re.I),
}


RIF_REQUIRED_HEADERS: dict[str, set[str]] = {
    RIF_ENVOLVIDOS: {
        "indexador",
        "cpfcnpjenvolvido",
        "nomeenvolvido",
        "tipoenvolvido",
        "agenciaenvolvido",
        "contaenvolvido",
    },
    RIF_OCORRENCIAS: {"indexador", "idocorrencia", "ocorrencia"},
    RIF_COMUNICACOES: {
        "indexador",
        "idcomunicacao",
        "numeroocorrenciabc",
        "data_do_recebimento",
        "data_da_operacao",
        "cpfcnpjcomunicante",
        "nomecomunicante",
        "informacoesadicionais",
        "codigosegmento",
    },
}


RIF_COLUMN_ENTITY_TYPES: dict[str, dict[str, EntityType]] = {
    RIF_ENVOLVIDOS: {
        "cpfcnpjenvolvido": EntityType.other_identifier,
        "nomeenvolvido": EntityType.person,
        "agenciaenvolvido": EntityType.bank_branch,
        "contaenvolvido": EntityType.bank_account,
    },
    RIF_OCORRENCIAS: {},
    RIF_COMUNICACOES: {},
}


RIF_PRESERVED_COLUMNS: dict[str, set[str]] = {
    RIF_ENVOLVIDOS: {
        "indexador",
        "tipoenvolvido",
        "dataaberturaconta",
        "dataatualizacaoconta",
        "bitpepcitado",
        "bitpessoaobrigadacitado",
        "intservidorcitado",
    },
    RIF_OCORRENCIAS: {"indexador", "idocorrencia", "ocorrencia"},
    RIF_COMUNICACOES: {
        "indexador",
        "idcomunicacao",
        "numeroocorrenciabc",
        "data_do_recebimento",
        "data_da_operacao",
        "datafimfato",
        "cpfcnpjcomunicante",
        "nomecomunicante",
        "cidadeagencia",
        "ufagencia",
        "nomeagencia",
        "numeroagencia",
        "campoa",
        "campob",
        "campoc",
        "campod",
        "campoe",
        "codigosegmento",
    },
}


def normalize_rif_header(value: str) -> str:
    return re.sub(r"[^a-z0-9_]", "", (value or "").strip().strip('"').lower())


def detect_rif_csv_subtype(text: str, filename: str | None = None) -> str:
    if filename:
        name = filename.replace("\\", "/").rsplit("/", 1)[-1]
        for subtype, pattern in RIF_FILENAME_PATTERNS.items():
            if pattern.fullmatch(name):
                return subtype

    headers = _headers_from_text(text)
    if not headers:
        return RIF_UNKNOWN

    header_set = set(headers)
    for subtype, required in RIF_REQUIRED_HEADERS.items():
        if required.issubset(header_set):
            return subtype
    return RIF_UNKNOWN


def rif_column_types_for_headers(headers: list[str], subtype: str) -> dict[int, EntityType]:
    rules = RIF_COLUMN_ENTITY_TYPES.get(subtype, {})
    return {index: rules[header] for index, header in enumerate(headers) if header in rules}


def rif_subtype_label(subtype: str) -> str:
    return {
        RIF_ENVOLVIDOS: "RIF Envolvidos",
        RIF_OCORRENCIAS: "RIF Ocorrencias",
        RIF_COMUNICACOES: "RIF Comunicacoes",
    }.get(subtype, "RIF nao classificado")


def _headers_from_text(text: str) -> list[str]:
    for line in text.splitlines():
        delimiter = ";" if line.count(";") >= line.count(",") and ";" in line else "," if "," in line else None
        if not delimiter:
            continue
        headers = [normalize_rif_header(cell) for cell in line.rstrip("\r\n").split(delimiter)]
        if "indexador" in headers:
            return headers
    return []
