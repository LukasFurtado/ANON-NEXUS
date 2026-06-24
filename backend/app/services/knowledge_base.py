import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.models.schemas import DocumentKind


PROJECT_ROOT = Path(__file__).resolve().parents[3]
KNOWLEDGE_PATH = PROJECT_ROOT / "backend" / "resources" / "knowledge" / "anon_operational_knowledge.json"


@lru_cache(maxsize=1)
def get_knowledge() -> dict[str, Any]:
    try:
        data = json.loads(KNOWLEDGE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _fallback_knowledge()
    return data if isinstance(data, dict) else _fallback_knowledge()


def json_contract_prompt() -> str:
    contract = get_knowledge().get("json_contract") or {}
    fields = ", ".join(contract.get("required_entity_fields") or ["type", "text"])
    recommended = ", ".join(contract.get("recommended_entity_fields") or ["start", "end"])
    forbidden = "; ".join(contract.get("forbidden_outputs") or [])
    empty = contract.get("accepted_empty_response") or '{"entities":[]}'
    return (
        "CONTRATO JSON OPERACIONAL DO ANON:\n"
        f"- Raiz obrigatoria: {contract.get('required_root', 'entities')}.\n"
        f"- Campos obrigatorios por entidade: {fields}.\n"
        f"- Campos recomendados para auditoria: {recommended}.\n"
        f"- Sem entidades: responder exatamente {empty}.\n"
        f"- Saidas proibidas: {forbidden}.\n"
        "- A IA apenas indica entidades; o backend aplica substituicoes e exporta."
    )


def compact_profile_guidance(document_kind: DocumentKind | str) -> str:
    profile = profile_knowledge(document_kind)
    if not profile:
        return ""
    must_anonymize = "; ".join(profile.get("must_anonymize") or [])
    must_preserve = "; ".join(profile.get("must_preserve") or [])
    protected_terms = "; ".join((profile.get("protected_terms") or [])[:14])
    return (
        "CONHECIMENTO OPERACIONAL DO PERFIL:\n"
        f"- Foco: {profile.get('focus', '')}\n"
        f"- Anonimizar: {must_anonymize}\n"
        f"- Preservar: {must_preserve}\n"
        f"- Termos tecnicos protegidos: {protected_terms}\n"
        f"- Orientacao: {profile.get('prompt_guidance', '')}"
    )


def profile_knowledge(document_kind: DocumentKind | str) -> dict[str, Any]:
    key = document_kind.value if isinstance(document_kind, DocumentKind) else str(document_kind)
    profiles = get_knowledge().get("profiles") or {}
    profile = profiles.get(key)
    return profile if isinstance(profile, dict) else {}


def protected_terms_for_profile(document_kind: DocumentKind | str) -> list[str]:
    profile = profile_knowledge(document_kind)
    return [str(item) for item in profile.get("protected_terms") or []]


def diagnostic_guidance() -> dict[str, str]:
    guidance = get_knowledge().get("diagnostic_guidance") or {}
    return {str(key): str(value) for key, value in guidance.items()} if isinstance(guidance, dict) else {}


def _fallback_knowledge() -> dict[str, Any]:
    return {
        "json_contract": {
            "required_root": "entities",
            "required_entity_fields": ["type", "text"],
            "recommended_entity_fields": ["start", "end"],
            "accepted_empty_response": '{"entities":[]}',
            "forbidden_outputs": ["markdown", "explicacao fora do JSON", "texto anonimizado"],
        },
        "profiles": {},
        "diagnostic_guidance": {
            "json_refusal": "JSON recusado significa resposta sem estrutura auditavel.",
            "warnings_file": "O arquivo Avisos concentra pontos de revisao.",
        },
    }
