import json
import re
import urllib.error
import urllib.request

from app.core.config import settings
from app.models.schemas import DocumentKind, Entity, EntityType
from app.pipeline.profile_strategy import profile_prompt


SYSTEM_PROMPT = """
Voce e um motor local de anonimização documental. Responda somente JSON valido.
Modo de raciocinio visivel desativado. Nunca emita pensamento, chain-of-thought,
deliberacao, tags <think>, explicacoes internas ou comentarios fora do JSON.
Identifique apenas dados pessoais, identificadores, pessoas, empresas e contatos.
Nao marque datas, valores monetarios, percentuais, artigos de lei, jurisprudencia,
fundamentacao juridica, conclusoes tecnicas ou analise financeira.
Formato: [{"type":"PERSON","text":"...","start":0,"end":10}]
Indices devem usar offsets exatos no texto recebido.
"""

NO_THINK_PREFIX = "/no_think"
THINK_BLOCK_PATTERN = re.compile(r"<think>.*?</think>", re.I | re.S)


def detect_entities_with_ollama(text: str, model: str, document_kind: DocumentKind = DocumentKind.auto) -> list[Entity]:
    if not text.strip():
        return []

    payload = {
        "model": model,
        "stream": False,
        "prompt": f"{NO_THINK_PREFIX}\n{SYSTEM_PROMPT}\n\n{profile_prompt(document_kind)}\n\nTEXTO:\n{text[:12000]}",
        "think": False,
        "options": {"temperature": 0},
    }

    request = urllib.request.Request(
        f"{settings.ollama_url}/api/generate",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            raw = json.loads(response.read().decode("utf-8")).get("response", "[]")
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return []

    raw = _strip_thinking(raw)
    try:
        items = json.loads(raw)
    except json.JSONDecodeError:
        return []

    entities: list[Entity] = []
    for item in items:
        try:
            entities.append(
                Entity(
                    type=EntityType(item["type"]),
                    text=item["text"],
                    start=int(item["start"]),
                    end=int(item["end"]),
                    source="ollama",
                )
            )
        except (KeyError, ValueError, TypeError):
            continue
    return entities


def _strip_thinking(value: str) -> str:
    cleaned = THINK_BLOCK_PATTERN.sub("", value).strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned.removeprefix("```json").removesuffix("```").strip()
    elif cleaned.startswith("```"):
        cleaned = cleaned.removeprefix("```").removesuffix("```").strip()
    return cleaned
