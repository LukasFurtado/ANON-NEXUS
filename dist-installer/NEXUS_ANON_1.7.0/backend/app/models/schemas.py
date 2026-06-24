from enum import Enum
from pydantic import BaseModel, Field


class DocumentKind(str, Enum):
    auto = "auto"
    rif = "rif"
    inquerito = "inquerito"
    relatorio = "relatorio"
    oficio = "oficio"
    administrativo = "administrativo"


class EntityType(str, Enum):
    person = "PERSON"
    organization = "ORGANIZATION"
    cpf = "CPF"
    cnpj = "CNPJ"
    rg = "RG"
    cnh = "CNH"
    passport = "PASSPORT"
    pis_nis = "PIS_NIS"
    functional_id = "FUNCTIONAL_ID"
    bank_account = "BANK_ACCOUNT"
    bank_branch = "BANK_BRANCH"
    pix = "PIX"
    boleto = "BOLETO"
    card = "CARD"
    phone = "PHONE"
    email = "EMAIL"
    address = "ADDRESS"
    cep = "CEP"
    vehicle_plate = "VEHICLE_PLATE"
    renavam = "RENAVAM"
    chassis = "CHASSIS"
    ip = "IP"
    mac = "MAC"
    qr_code = "QR_CODE"
    protocol = "PROTOCOL"
    proceeding = "PROCEEDING"
    other_identifier = "OTHER_IDENTIFIER"


class Entity(BaseModel):
    type: EntityType
    text: str
    start: int
    end: int
    source: str = Field(description="regex, ollama, ocr or validator")


class AnonymizationStats(BaseModel):
    entities_found: int
    replacements_applied: int
    preserved_dates: int
    preserved_values: int
    validation_warnings: list[str] = []


class AnonymizationControlRow(BaseModel):
    original_value: str
    entity_type: str
    anonymous_id: str
    occurrences: int


class AuditInfo(BaseModel):
    source_sha256: str
    export_sha256: dict[str, str]
    processing_time_seconds: float
    ocr_used: bool
    structure_preserved: bool
    validation_status: str


class AnonymizationResult(BaseModel):
    job_id: str
    original_filename: str
    document_kind: DocumentKind
    model: str
    original_text: str
    anonymized_text: str
    entities: list[Entity]
    control_table: list[AnonymizationControlRow] = []
    stats: AnonymizationStats
    audit: AuditInfo
    export_paths: dict[str, str]


class BatchAnonymizationResult(BaseModel):
    group_id: str
    request_title: str | None = None
    results: list[AnonymizationResult]
    log_sha256: str | None = None


class AnonymizeOptions(BaseModel):
    document_kind: DocumentKind = DocumentKind.auto
    model: str = "NEXUS-anon:latest"
    use_ollama: bool = True
    preserve_layout: bool = True
    request_title: str | None = None
