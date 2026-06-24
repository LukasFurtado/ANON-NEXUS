import json
import re
import urllib.error
import urllib.request

from app.core.config import settings
from app.models.schemas import DocumentKind, Entity, EntityType
from app.pipeline.profile_strategy import profile_prompt


SYSTEM_PROMPT = """
Voce e um motor local obrigatorio de anonimização documental. Responda somente JSON valido.
Modo de raciocinio visivel desativado. Nunca emita pensamento, chain-of-thought,
deliberacao, tags <think>, explicacoes internas ou comentarios fora do JSON.
Sua funcao nao e modificar, interpretar, resumir, reescrever, complementar ou gerar documentos.
Sua unica tarefa e indicar entidades existentes no texto que possam identificar pessoas fisicas ou juridicas.
Nao gere texto anonimizado, CSV, DOCX, PDF, resumo, tabela, justificativa, comentario ou nova versao do documento.
As substituicoes, identificadores anonimos e exportacoes sao responsabilidade exclusiva do backend.
Analise todo o trecho recebido e indique tambem entidades evidentes, ainda que parecam detectaveis por regra deterministica.
Identifique apenas dados pessoais, identificadores, pessoas, empresas e contatos.
Nao marque datas, valores monetarios, percentuais, artigos de lei, jurisprudencia,
fundamentacao juridica, conclusoes tecnicas ou analise financeira.
Formato: [{"type":"PERSON","text":"...","start":0,"end":10}]
Types permitidos: PERSON, ORGANIZATION, CPF, CNPJ, RG, CNH, PASSPORT, PIS_NIS,
FUNCTIONAL_ID, BANK_ACCOUNT, BANK_BRANCH, PIX, BOLETO, CARD, PHONE, EMAIL,
ADDRESS, CEP, VEHICLE_PLATE, RENAVAM, CHASSIS, IP, MAC, QR_CODE, PROTOCOL,
PROCEEDING, OTHER_IDENTIFIER.
Indices devem usar offsets exatos no texto recebido.
O campo "text" deve ser copia literal do trecho encontrado entre "start" e "end".
"""

NO_THINK_PREFIX = "/no_think"
THINK_BLOCK_PATTERN = re.compile(r"<think>.*?</think>", re.I | re.S)


class OllamaDetectionError(RuntimeError):
    pass


def detect_entities_with_ollama(text: str, model: str, document_kind: DocumentKind) -> list[Entity]:
    if not text.strip():
        return []

    entities: list[Entity] = []
    for chunk_start, chunk in _iter_text_chunks(text):
        entities.extend(_detect_entities_with_ollama_chunk(chunk, chunk_start, model, document_kind))
    return _deduplicate_entities(entities)


def _detect_entities_with_ollama_chunk(
    text: str,
    chunk_start: int,
    model: str,
    document_kind: DocumentKind,
) -> list[Entity]:
    payload = {
        "model": model,
        "stream": False,
        "prompt": f"{NO_THINK_PREFIX}\n{SYSTEM_PROMPT}\n\n{profile_prompt(document_kind)}\n\nTEXTO:\n{text}",
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
    except urllib.error.HTTPError as exc:
        raise OllamaDetectionError(f"modelo local indisponivel ou recusado pelo Ollama ({exc.code}).") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise OllamaDetectionError("Ollama local nao respondeu dentro do tempo esperado.") from exc
    except json.JSONDecodeError as exc:
        raise OllamaDetectionError("Ollama retornou resposta sem JSON valido.") from exc

    raw = _strip_thinking(raw)
    try:
        items = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise OllamaDetectionError("modelo local nao retornou a lista JSON de entidades esperada.") from exc
    if not isinstance(items, list):
        raise OllamaDetectionError("modelo local retornou formato inesperado; era esperada uma lista JSON.")

    entities: list[Entity] = []
    for item in items:
        try:
            start = int(item["start"])
            end = int(item["end"])
            entity_text = item["text"]
            entity_type = _normalize_entity_type(str(item["type"]))
            if entity_type is None:
                continue
            resolved = _resolve_span(text, entity_text, start, end)
            if resolved is None:
                continue
            start, end = resolved
            entities.append(
                Entity(
                    type=entity_type,
                    text=entity_text,
                    start=chunk_start + start,
                    end=chunk_start + end,
                    source="ollama",
                )
            )
        except (KeyError, ValueError, TypeError):
            continue
    return entities


def _normalize_entity_type(value: str) -> EntityType | None:
    normalized = value.strip().upper()
    aliases = {
        "NAME": "PERSON",
        "NOME": "PERSON",
        "PESSOA": "PERSON",
        "COMPANY": "ORGANIZATION",
        "EMPRESA": "ORGANIZATION",
        "ACCOUNT": "BANK_ACCOUNT",
        "ACCOUNT_NUMBER": "BANK_ACCOUNT",
        "CONTA": "BANK_ACCOUNT",
        "BANK_AGENCY": "BANK_BRANCH",
        "AGENCY": "BANK_BRANCH",
        "AGENCIA": "BANK_BRANCH",
        "DOCUMENT": "OTHER_IDENTIFIER",
        "DOCUMENTO": "OTHER_IDENTIFIER",
        "ID": "OTHER_IDENTIFIER",
        "IDENTIFIER": "OTHER_IDENTIFIER",
        "IDENTIFICADOR": "OTHER_IDENTIFIER",
        "VEHICLE": "VEHICLE_PLATE",
    }
    normalized = aliases.get(normalized, normalized)
    blocked = {"VALUE", "AMOUNT", "MONEY", "DATE", "TIME", "PERCENTAGE", "HISTORY", "DESCRIPTION"}
    if normalized in blocked:
        return None
    try:
        return EntityType(normalized)
    except ValueError:
        return None


def _resolve_span(text: str, entity_text: str, start: int, end: int) -> tuple[int, int] | None:
    if start >= 0 and end > start and end <= len(text) and text[start:end] == entity_text:
        return start, end

    positions: list[int] = []
    cursor = text.find(entity_text)
    while cursor >= 0:
        positions.append(cursor)
        cursor = text.find(entity_text, cursor + 1)
    if not positions:
        return None
    best = min(positions, key=lambda position: abs(position - max(start, 0)))
    return best, best + len(entity_text)


def _iter_text_chunks(text: str, max_chars: int = 12000) -> list[tuple[int, str]]:
    chunks: list[tuple[int, str]] = []
    start = 0
    length = len(text)
    while start < length:
        end = min(start + max_chars, length)
        if end < length:
            line_break = text.rfind("\n", start, end)
            if line_break > start + max_chars // 2:
                end = line_break + 1
        chunks.append((start, text[start:end]))
        start = end
    return chunks


def _deduplicate_entities(entities: list[Entity]) -> list[Entity]:
    seen: set[tuple[int, int, str]] = set()
    unique: list[Entity] = []
    for entity in sorted(entities, key=lambda item: (item.start, item.end, item.type.value)):
        key = (entity.start, entity.end, entity.type.value)
        if key in seen:
            continue
        seen.add(key)
        unique.append(entity)
    return unique


def _strip_thinking(value: str) -> str:
    cleaned = THINK_BLOCK_PATTERN.sub("", value).strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned.removeprefix("```json").removesuffix("```").strip()
    elif cleaned.startswith("```"):
        cleaned = cleaned.removeprefix("```").removesuffix("```").strip()
    return cleaned
