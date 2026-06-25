import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
NAME_LIBRARY_PATH = PROJECT_ROOT / "backend" / "resources" / "knowledge" / "brazilian_name_library.json"


@lru_cache(maxsize=1)
def brazilian_name_library() -> dict[str, set[str]]:
    try:
        payload = json.loads(NAME_LIBRARY_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        payload = {}
    return {
        "first_names": {_normalize(item) for item in payload.get("first_names", [])},
        "surnames": {_normalize(item) for item in payload.get("surnames", [])},
        "particles": {_normalize(item) for item in payload.get("particles", [])} or {"de", "da", "do", "das", "dos", "e"},
        "context_terms": {_normalize(item) for item in payload.get("context_terms", [])},
    }


def first_names() -> set[str]:
    return set(brazilian_name_library()["first_names"])


def surnames() -> set[str]:
    return set(brazilian_name_library()["surnames"])


def name_particles() -> set[str]:
    return set(brazilian_name_library()["particles"])


def _normalize(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value or "")
    no_accent = "".join(char for char in decomposed if not unicodedata.combining(char))
    cleaned = re.sub(r"[^a-zA-Z0-9]+", " ", no_accent.lower())
    return re.sub(r"\s+", " ", cleaned).strip()
