from enum import Enum
from pydantic import BaseModel, Field


class DocumentKind(str, Enum):
    rif = "rif"
    extrato_bancario = "extrato_bancario"
    relatorio_investigativo = "relatorio_investigativo"
    personalizado = "personalizado"


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
    confidence: float | None = None
    reason: str | None = None
    action: str | None = None


class AnonymizationStats(BaseModel):
    entities_found: int
    replacements_applied: int
    preserved_dates: int
    preserved_values: int
    validation_warnings: list[str] = []
    ollama_chunks_processed: int = 0
    ollama_json_rejected_chunks: int = 0
    ollama_correction_attempts: int = 0
    ollama_correction_successes: int = 0
    ollama_json_rejection_reasons: list[str] = Field(default_factory=list)
    ollama_failure_reason: str | None = None
    ollama_preserved_items: int = 0
    post_validation_warnings: list[str] = Field(default_factory=list)
    post_validation_score: int | None = None
    communication_events: list[dict] = Field(default_factory=list)
    communication_summary: dict = Field(default_factory=dict)
    quality_status: str | None = None
    quality_score: int | None = None
    quality_reasons: list[str] = Field(default_factory=list)
    confidence_score: int | None = None
    confidence_level: str | None = None
    confidence_reasons: list[str] = Field(default_factory=list)
    sync_entries_loaded: int = 0
    sync_entities_found: int = 0
    nce_dictionary_size: int = 0
    consistency_status: str = "Nao avaliada"
    consistency_notes: list[str] = Field(default_factory=list)


class AnonymizationControlRow(BaseModel):
    original_value: str
    entity_type: str
    anonymous_id: str
    occurrences: int


class AnonymizationSyncEntry(BaseModel):
    original_value: str
    entity_type: EntityType
    anonymous_id: str
    source: str = "sync_package"


class HumanReviewItem(BaseModel):
    id: str
    category: str
    label: str
    status: str = "pendente"
    recommendation: str
    severity: str = "media"
    metadata: dict = Field(default_factory=dict)


class AuditInfo(BaseModel):
    source_sha256: str
    export_sha256: dict[str, str]
    export_sha256_reason: dict[str, str] = Field(default_factory=dict)
    processing_time_seconds: float
    ocr_used: bool
    structure_preserved: bool
    validation_status: str
    anon_version: str | None = None
    safe_summary_id: str | None = None
    pipeline_state_id: str | None = None


class AnonymizationResult(BaseModel):
    job_id: str
    original_filename: str
    document_kind: DocumentKind
    model: str
    original_text: str
    anonymized_text: str
    entities: list[Entity]
    control_table: list[AnonymizationControlRow] = []
    review_items: list[HumanReviewItem] = []
    stats: AnonymizationStats
    audit: AuditInfo
    export_paths: dict[str, str]
    safe_summary: dict = Field(default_factory=dict)
    pipeline_state: dict = Field(default_factory=dict)


class BatchAnonymizationResult(BaseModel):
    group_id: str
    request_title: str | None = None
    results: list[AnonymizationResult]
    log_sha256: str | None = None


class AnonymizeOptions(BaseModel):
    document_kind: DocumentKind
    model: str = "qwen3:32b"
    use_ollama: bool = True
    preserve_layout: bool = True
    request_title: str | None = None
    sync_entries: list[AnonymizationSyncEntry] = Field(default_factory=list)


class ManualCorrection(BaseModel):
    original_value: str
    entity_type: EntityType = EntityType.person
    anonymous_id: str | None = None


class ManualReanalysisRequest(BaseModel):
    corrections: list[ManualCorrection]
    note: str | None = None
