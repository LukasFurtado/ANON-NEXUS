import json
from functools import lru_cache
from pathlib import Path
from typing import Any


PROFILE_DIR = Path(__file__).resolve().parents[2] / "resources" / "profiles"


class ProfileNotFoundError(LookupError):
    def __init__(self, profile_id: str, available: list[str]) -> None:
        suggestion = ", ".join(available) if available else "nenhum perfil disponivel"
        super().__init__(f"Perfil documental nao encontrado: {profile_id}. Perfis disponiveis: {suggestion}.")
        self.profile_id = profile_id
        self.available = available


def available_profiles() -> list[str]:
    if not PROFILE_DIR.exists():
        return []
    return sorted(path.stem for path in PROFILE_DIR.glob("*.json"))


@lru_cache(maxsize=16)
def load_profile(profile_id: str) -> dict[str, Any]:
    normalized = profile_id.strip().lower()
    path = PROFILE_DIR / f"{normalized}.json"
    if not path.exists():
        raise ProfileNotFoundError(normalized, available_profiles())
    with path.open("r", encoding="utf-8") as file:
        payload = json.load(file)
    payload.setdefault("profile_id", normalized)
    return payload


def profile_context_prompt(profile_id: str) -> str:
    profile = load_profile(profile_id)
    lines = [
        f"Voce esta operando sobre um documento do tipo {profile.get('profile_id')} - {profile.get('display_name')}.",
        f"Preserve obrigatoriamente, nunca anonimize: {', '.join(profile.get('preserve_always', []))}.",
        f"Anonimize obrigatoriamente: {', '.join(profile.get('anonymize_always', []))}.",
        (
            f"Campos ambiguos, resolucao {profile.get('ambiguity_resolution', 'conservador')}: "
            f"{', '.join(profile.get('ambiguous_fields', []))}."
        ),
    ]
    delos = profile.get("delos_reverse_engineering")
    if isinstance(delos, dict):
        lines.extend(_delos_reverse_engineering_prompt(delos))
    rif = profile.get("rif_reverse_engineering")
    if isinstance(rif, dict):
        lines.extend(_rif_reverse_engineering_prompt(rif))
    return "\n".join(lines)


def _delos_reverse_engineering_prompt(delos: dict[str, Any]) -> list[str]:
    column_semantics = delos.get("column_semantics") if isinstance(delos.get("column_semantics"), dict) else {}
    protected = delos.get("protected_operation_patterns") if isinstance(delos.get("protected_operation_patterns"), list) else []
    ambiguities = delos.get("ambiguity_rules") if isinstance(delos.get("ambiguity_rules"), list) else []
    llm_rules = delos.get("llm_rules") if isinstance(delos.get("llm_rules"), list) else []
    validation_targets = delos.get("validation_targets") if isinstance(delos.get("validation_targets"), list) else []
    return [
        "Engenharia reversa DELOS ativa para extrato bancario.",
        "Semantica de colunas: "
        + "; ".join(f"{key}={value}" for key, value in list(column_semantics.items())[:12]),
        "Padroes operacionais protegidos: " + ", ".join(str(item) for item in protected[:18]) + ".",
        "Regras de ambiguidade: " + " ".join(str(item) for item in ambiguities[:5]),
        "Regras para IA local: " + " ".join(str(item) for item in llm_rules[:6]),
        "Alvos de validacao: " + ", ".join(str(item) for item in validation_targets[:8]) + ".",
    ]


def _rif_reverse_engineering_prompt(rif: dict[str, Any]) -> list[str]:
    patterns = rif.get("filename_patterns") if isinstance(rif.get("filename_patterns"), dict) else {}
    subtypes = rif.get("subtypes") if isinstance(rif.get("subtypes"), dict) else {}
    cross_rules = rif.get("cross_file_rules") if isinstance(rif.get("cross_file_rules"), list) else []
    subtype_lines = []
    for name, spec in list(subtypes.items())[:3]:
        if not isinstance(spec, dict):
            continue
        anonymize = ", ".join(str(item) for item in spec.get("anonymize_columns") or spec.get("anonymize_inside_narrative") or [])
        preserve = ", ".join(str(item) for item in (spec.get("preserve_columns") or [])[:12])
        subtype_lines.append(f"{name}: anonimizar [{anonymize}], preservar [{preserve}]")
    return [
        "Engenharia reversa RIF ativa para CSVs COAF.",
        "Padroes de arquivo: " + "; ".join(f"{key}={value}" for key, value in patterns.items()),
        "Modelos conhecidos: " + " | ".join(subtype_lines),
        "Regras entre arquivos: " + " ".join(str(item) for item in cross_rules[:4]),
    ]
