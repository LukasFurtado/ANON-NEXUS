import re
import unicodedata
from functools import lru_cache

from app.services.knowledge_base import institutional_library


@lru_cache(maxsize=1)
def institution_terms() -> frozenset[str]:
    data = institutional_library()
    categories = data.get("institutional_categories") if isinstance(data, dict) else {}
    terms: set[str] = set()
    if isinstance(categories, dict):
        for values in categories.values():
            if isinstance(values, list):
                terms.update(_normalize_text(str(item)) for item in values if str(item).strip())
    return frozenset(term for term in terms if term)


def is_institutional_retention(value: str) -> bool:
    normalized = _normalize_text(value)
    if not normalized:
        return False
    terms = institution_terms()
    if normalized in terms:
        return True
    if len(normalized) < 4:
        return False
    return any(_contains_term(normalized, term) for term in terms if len(term) >= 4)


def retention_reason(value: str) -> str | None:
    if is_institutional_retention(value):
        return "biblioteca institucional preservou orgao publico, banco ou entidade operacional."
    return None


def _contains_term(value: str, term: str) -> bool:
    pattern = rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])"
    return re.search(pattern, value) is not None


def _normalize_text(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value or "")
    no_accent = "".join(char for char in decomposed if not unicodedata.combining(char))
    cleaned = re.sub(r"[^a-zA-Z0-9]+", " ", no_accent.lower())
    return re.sub(r"\s+", " ", cleaned).strip()
