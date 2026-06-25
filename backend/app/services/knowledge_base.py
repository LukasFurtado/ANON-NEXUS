import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.models.schemas import DocumentKind


PROJECT_ROOT = Path(__file__).resolve().parents[3]
KNOWLEDGE_PATH = PROJECT_ROOT / "backend" / "resources" / "knowledge" / "anon_operational_knowledge.json"
INSTITUTIONAL_LIBRARY_PATH = PROJECT_ROOT / "backend" / "resources" / "knowledge" / "institutional_retention_library.json"


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
    actions = ", ".join(contract.get("accepted_actions") or ["anonymize", "preserve", "review"])
    types = ", ".join(contract.get("entity_type_catalog") or [])
    forbidden = "; ".join(contract.get("forbidden_outputs") or [])
    empty = contract.get("accepted_empty_response") or '{"entities":[]}'
    example = contract.get("example_response") or '{"entities":[{"type":"PERSON","text":"JOAO DA SILVA","action":"anonymize"}]}'
    return (
        "CONTRATO JSON OPERACIONAL DO ANON:\n"
        f"- Raiz obrigatoria: {contract.get('required_root', 'entities')}.\n"
        f"- Campos obrigatorios por entidade: {fields}.\n"
        f"- Campos recomendados para auditoria: {recommended}.\n"
        f"- Acoes aceitas: {actions}. Use preserve quando reconhecer termo institucional que nao deve ser anonimizado.\n"
        f"- Tipos aceitos: {types}.\n"
        f"- Sem entidades: responder exatamente {empty}.\n"
        f"- Exemplo valido: {example}.\n"
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
    lines = [
        "CONHECIMENTO OPERACIONAL DO PERFIL:\n"
        f"- Foco: {profile.get('focus', '')}\n"
        f"- Anonimizar: {must_anonymize}\n"
        f"- Preservar: {must_preserve}\n"
        f"- Termos tecnicos protegidos: {protected_terms}\n"
        f"- Orientacao: {profile.get('prompt_guidance', '')}"
    ]
    delos = profile.get("delos_reverse_engineering")
    if isinstance(delos, dict):
        column_rules = "; ".join(str(item) for item in (delos.get("column_rules") or [])[:4])
        ambiguity_rules = "; ".join(str(item) for item in (delos.get("ambiguity_rules") or [])[:4])
        validation_focus = "; ".join(str(item) for item in (delos.get("validation_focus") or [])[:6])
        lines.append(
            "ENGENHARIA REVERSA DELOS:\n"
            f"- Regras de coluna: {column_rules}\n"
            f"- Ambiguidades conhecidas: {ambiguity_rules}\n"
            f"- Validacao prioritaria: {validation_focus}"
        )
    rif = profile.get("rif_reverse_engineering")
    if isinstance(rif, dict):
        patterns = rif.get("filename_patterns") if isinstance(rif.get("filename_patterns"), dict) else {}
        subtypes = rif.get("subtypes") if isinstance(rif.get("subtypes"), dict) else {}
        subtype_names = "; ".join(str(key) for key in subtypes.keys())
        cross_rules = "; ".join(str(item) for item in (rif.get("cross_file_rules") or [])[:4])
        lines.append(
            "ENGENHARIA REVERSA RIF:\n"
            f"- Padroes de nome: {'; '.join(f'{key}={value}' for key, value in patterns.items())}\n"
            f"- Subtipos reconhecidos: {subtype_names}\n"
            f"- Regras centrais: {cross_rules}"
        )
    return "\n".join(lines)


def specialized_behavior_prompt() -> str:
    knowledge = get_knowledge()
    rules = "; ".join(knowledge.get("communication_rules") or [])
    detector_suite = knowledge.get("detector_suite") if isinstance(knowledge.get("detector_suite"), dict) else {}
    detector_precedence = ", ".join(str(item) for item in detector_suite.get("precedence") or [])
    detector_guidance = str(detector_suite.get("llm_guidance") or "")
    nce_core = knowledge.get("nce_core") if isinstance(knowledge.get("nce_core"), dict) else {}
    nce_rules = "; ".join(str(item) for item in (nce_core.get("consistency_rules") or [])[:4])
    protocol = knowledge.get("cell_protocol") or {}
    cells = protocol.get("cells") if isinstance(protocol, dict) else {}
    cell_lines = []
    if isinstance(cells, dict):
        for name, info in cells.items():
            if not isinstance(info, dict):
                continue
            needs = ", ".join(str(item) for item in info.get("needs") or [])
            offers = ", ".join(str(item) for item in info.get("offers") or [])
            cell_lines.append(f"- {name}: precisa de [{needs}] e oferece [{offers}]")
    return (
        "NUCLEO DE COMPORTAMENTO ESPECIALIZADO DO ANON:\n"
        "- Nome tecnico: NCE-ANON.\n"
        "- Objetivo: alinhar IA local, regex, perfis, validador, substituidor, exportador e auditoria.\n"
        f"- NCE central: {nce_core.get('purpose', '')}\n"
        f"- Regras de consistencia do NCE: {nce_rules}\n"
        "- A IA local deve obedecer ao contrato JSON e atuar somente como detector semantico de entidades.\n"
        "- O backend preserva documento, aplica substituicoes, calcula hashes, valida e exporta.\n"
        f"- Suite deterministica previa: {detector_precedence}\n"
        f"- Orientacao da suite para IA local: {detector_guidance}\n"
        f"- Regras de comunicacao: {rules}\n"
        "- Protocolo entre celulas:\n"
        + "\n".join(cell_lines[:10])
    )


def profile_knowledge(document_kind: DocumentKind | str) -> dict[str, Any]:
    key = document_kind.value if isinstance(document_kind, DocumentKind) else str(document_kind)
    profiles = get_knowledge().get("profiles") or {}
    profile = profiles.get(key)
    return profile if isinstance(profile, dict) else {}


def protected_terms_for_profile(document_kind: DocumentKind | str) -> list[str]:
    profile = profile_knowledge(document_kind)
    return [str(item) for item in profile.get("protected_terms") or []]


@lru_cache(maxsize=1)
def institutional_library() -> dict[str, Any]:
    try:
        data = json.loads(INSTITUTIONAL_LIBRARY_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


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
