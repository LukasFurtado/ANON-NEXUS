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
    return "\n".join(
        [
            f"Voce esta operando sobre um documento do tipo {profile.get('profile_id')} - {profile.get('display_name')}.",
            f"Preserve obrigatoriamente, nunca anonimize: {', '.join(profile.get('preserve_always', []))}.",
            f"Anonimize obrigatoriamente: {', '.join(profile.get('anonymize_always', []))}.",
            (
                f"Campos ambiguos, resolucao {profile.get('ambiguity_resolution', 'conservador')}: "
                f"{', '.join(profile.get('ambiguous_fields', []))}."
            ),
        ]
    )
