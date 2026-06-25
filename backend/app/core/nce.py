import re
import unicodedata
import uuid
from dataclasses import dataclass, field
from datetime import datetime

from app.models.schemas import DocumentKind
from app.pipeline.anonymizer import ReplacementState
from app.pipeline.rif_rules import RIF_COMUNICACOES, RIF_ENVOLVIDOS, RIF_OCORRENCIAS, detect_rif_csv_subtype, rif_subtype_label


@dataclass
class NCEStageRecord:
    stage: str
    status: str
    decision: str
    summary: str
    data: dict[str, object] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))


@dataclass
class NCEFileContext:
    filename: str
    document_kind: DocumentKind
    subtype: str
    role_label: str
    source_sha256: str = ""
    extension: str = ""
    text_length: int = 0
    expected_sensitive_domains: list[str] = field(default_factory=list)
    coordination_log: list[NCEStageRecord] = field(default_factory=list)

    def coordinate(
        self,
        *,
        stage: str,
        status: str = "authorized",
        decision: str = "continue",
        summary: str = "",
        **data: object,
    ) -> NCEStageRecord:
        record = NCEStageRecord(stage=stage, status=status, decision=decision, summary=summary, data=data)
        self.coordination_log.append(record)
        return record

    def public_metadata(self) -> dict[str, object]:
        return {
            "filename": self.filename,
            "document_kind": self.document_kind.value,
            "subtype": self.subtype,
            "role_label": self.role_label,
            "source_sha256": self.source_sha256,
            "extension": self.extension,
            "text_length": self.text_length,
            "expected_sensitive_domains": list(self.expected_sensitive_domains),
            "coordination_log": [
                {
                    "stage": item.stage,
                    "status": item.status,
                    "decision": item.decision,
                    "summary": item.summary,
                    "data": item.data,
                    "created_at": item.created_at,
                }
                for item in self.coordination_log
            ],
        }


@dataclass
class NCEGroupContext:
    group_id: str
    request_title: str | None
    document_kind: DocumentKind
    model: str
    replacement_state: ReplacementState = field(default_factory=ReplacementState)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    files: list[NCEFileContext] = field(default_factory=list)

    @classmethod
    def start(
        cls,
        *,
        request_title: str | None,
        document_kind: DocumentKind,
        model: str,
        replacement_state: ReplacementState | None = None,
    ) -> "NCEGroupContext":
        return cls(
            group_id=str(uuid.uuid4()),
            request_title=request_title,
            document_kind=document_kind,
            model=model,
            replacement_state=replacement_state or ReplacementState(),
        )

    def prepare_file(self, *, filename: str, text: str, source_sha256: str = "", extension: str = "") -> NCEFileContext:
        subtype = detect_document_subtype(self.document_kind, text, filename)
        context = NCEFileContext(
            filename=filename,
            document_kind=self.document_kind,
            subtype=subtype,
            role_label=document_role_label(self.document_kind, subtype),
            source_sha256=source_sha256,
            extension=extension,
            text_length=len(text),
            expected_sensitive_domains=expected_sensitive_domains(self.document_kind, subtype),
        )
        context.coordinate(
            stage="context",
            summary="Arquivo classificado pelo NCE e vinculado ao grupo de consistencia.",
            dictionary_size=len(self.replacement_state.replacements),
        )
        self.files.append(context)
        return context

    def coordinate(
        self,
        file_context: NCEFileContext,
        *,
        stage: str,
        status: str = "authorized",
        decision: str = "continue",
        summary: str = "",
        **data: object,
    ) -> NCEStageRecord:
        return file_context.coordinate(stage=stage, status=status, decision=decision, summary=summary, **data)

    def public_metadata(self) -> dict[str, object]:
        return {
            "nce_group_id": self.group_id,
            "request_title": self.request_title,
            "document_kind": self.document_kind.value,
            "model": self.model,
            "created_at": self.created_at,
            "files": [file.public_metadata() for file in self.files],
            "dictionary_size": len(self.replacement_state.replacements),
            "counters": dict(self.replacement_state.counters),
        }


def detect_document_subtype(document_kind: DocumentKind, text: str, filename: str | None = None) -> str:
    if document_kind == DocumentKind.rif:
        return detect_rif_csv_subtype(text, filename)
    return document_kind.value


def document_role_label(document_kind: DocumentKind, subtype: str) -> str:
    if document_kind == DocumentKind.rif:
        return rif_subtype_label(subtype)
    return {
        DocumentKind.extrato_bancario: "Extrato bancario",
        DocumentKind.relatorio_investigativo: "Relatorio investigativo",
        DocumentKind.personalizado: "Personalizado",
    }.get(document_kind, document_kind.value)


def expected_sensitive_domains(document_kind: DocumentKind, subtype: str) -> list[str]:
    if document_kind == DocumentKind.rif:
        if subtype == RIF_ENVOLVIDOS:
            return ["CPF/CNPJ", "nome", "agencia", "conta"]
        if subtype == RIF_COMUNICACOES:
            return ["narrativa", "pessoa", "CPF/CNPJ", "PIX", "conta", "contraparte"]
        if subtype == RIF_OCORRENCIAS:
            return ["narrativa operacional preservada", "identificador relacional"]
        return ["pessoa", "empresa", "CPF/CNPJ", "conta", "PIX"]
    if document_kind == DocumentKind.extrato_bancario:
        return ["titular", "CPF/CNPJ", "contraparte", "conta", "agencia", "PIX"]
    if document_kind == DocumentKind.relatorio_investigativo:
        return ["pessoa", "empresa", "CPF/CNPJ", "endereco", "telefone", "email", "processo"]
    if document_kind == DocumentKind.personalizado:
        return ["definidos pelo operador", "revisao humana", "marcadores manuais"]
    return ["identificadores pessoais"]


def canonical_entity_key(entity_type: str, original: str) -> str:
    value = original or ""
    if entity_type in {"CPF", "CNPJ", "PHONE", "CEP", "RG", "CNH", "PIS_NIS", "BANK_ACCOUNT", "BANK_BRANCH"}:
        digits = re.sub(r"\D", "", value)
        if entity_type == "CPF" and len(digits) == 12 and digits.startswith("0"):
            digits = digits[1:]
        if digits:
            return f"{entity_type}:{digits}"
    normalized = _normalize_text_for_key(value)
    return f"{entity_type}:{normalized}"


def _normalize_text_for_key(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value or "")
    no_accent = "".join(char for char in decomposed if not unicodedata.combining(char))
    no_punct = re.sub(r"[^\w\s]", " ", no_accent, flags=re.UNICODE)
    return re.sub(r"\s+", " ", no_punct.casefold()).strip()
