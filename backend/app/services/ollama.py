import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass

from app.core.config import settings
from app.core.profile_loader import profile_context_prompt
from app.models.schemas import DocumentKind, Entity, EntityType
from app.pipeline.profile_strategy import profile_prompt
from app.services.knowledge_base import compact_profile_guidance, json_contract_prompt, specialized_behavior_prompt


SYSTEM_PROMPT = """
Voce e um motor local obrigatorio de anonimizacao documental. Responda somente JSON valido.
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
Formato obrigatorio: {"entities":[{"type":"PERSON","text":"...","start":0,"end":10,"action":"anonymize","reason":"...","confidence":0.90}],"preserve":[{"text":"...","reason":"..."}]}
Se nenhuma entidade sensivel for localizada, responda exatamente: {"entities":[]}
Types permitidos: PERSON, ORGANIZATION, CPF, CNPJ, RG, CNH, PASSPORT, PIS_NIS,
FUNCTIONAL_ID, BANK_ACCOUNT, BANK_BRANCH, PIX, BOLETO, CARD, PHONE, EMAIL,
ADDRESS, CEP, VEHICLE_PLATE, RENAVAM, CHASSIS, IP, MAC, QR_CODE, PROTOCOL,
PROCEEDING, OTHER_IDENTIFIER.
Indices devem usar offsets exatos no texto recebido.
O campo "text" deve ser copia literal do trecho encontrado entre "start" e "end".
O campo "action" deve ser anonymize, preserve ou review. Use preserve somente para item tecnico que voce reconheceu e decidiu manter.
O campo "confidence" deve ser numero entre 0 e 1. O campo "reason" deve ser curto e sem dados sensiveis novos.
"""
NO_THINK_PREFIX = "/no_think"
THINK_BLOCK_PATTERN = re.compile(r"<think>.*?</think>", re.I | re.S)


class OllamaDetectionError(RuntimeError):
    pass


class OllamaResponseFormatError(OllamaDetectionError):
    pass


@dataclass
class OllamaDetectionResult:
    entities: list[Entity]
    chunks_processed: int = 0
    json_rejected_chunks: int = 0
    correction_attempts: int = 0
    correction_successes: int = 0
    json_rejection_reasons: list[str] | None = None
    preserved_items: int = 0


def detect_entities_with_ollama(text: str, model: str, document_kind: DocumentKind) -> OllamaDetectionResult:
    if not text.strip():
        return OllamaDetectionResult(entities=[])

    entities: list[Entity] = []
    result = OllamaDetectionResult(entities=entities)
    for chunk_start, chunk in _iter_text_chunks(text):
        chunk_result = _detect_entities_with_ollama_chunk(chunk, chunk_start, model, document_kind)
        result.chunks_processed += 1
        result.json_rejected_chunks += chunk_result.json_rejected_chunks
        result.correction_attempts += chunk_result.correction_attempts
        result.correction_successes += chunk_result.correction_successes
        result.preserved_items += chunk_result.preserved_items
        if chunk_result.json_rejection_reasons:
            result.json_rejection_reasons = [
                *(result.json_rejection_reasons or []),
                *chunk_result.json_rejection_reasons,
            ]
        entities.extend(chunk_result.entities)
    result.entities = _deduplicate_entities(entities)
    return result


def _detect_entities_with_ollama_chunk(
    text: str,
    chunk_start: int,
    model: str,
    document_kind: DocumentKind,
) -> OllamaDetectionResult:
    payload = {
        "model": model,
        "stream": False,
        "format": "json",
        "prompt": (
            f"{NO_THINK_PREFIX}\n"
            f"{SYSTEM_PROMPT}\n\n"
            f"{specialized_behavior_prompt()}\n\n"
            f"{json_contract_prompt()}\n\n"
            f"{profile_context_prompt(document_kind.value)}\n\n"
            f"{profile_prompt(document_kind)}\n\n"
            f"{compact_profile_guidance(document_kind)}\n\n"
            f"TEXTO:\n{text}"
        ),
        "think": False,
        "options": {"temperature": 0, "top_p": 0.9, "repeat_penalty": 1.1, "num_predict": 4096},
    }

    raw = _request_ollama_generate(payload)
    json_rejected = 0
    correction_attempts = 0
    correction_successes = 0
    rejection_reasons: list[str] = []
    try:
        items = _load_entity_items(raw)
    except OllamaResponseFormatError:
        json_rejected = 1
        rejection_reasons.append("Resposta inicial fora do contrato JSON de entidades.")
        correction_attempts = 1
        corrected_raw = _request_ollama_generate(_correction_payload(raw, model))
        try:
            items = _load_entity_items(corrected_raw)
            correction_successes = 1
        except OllamaResponseFormatError:
            rejection_reasons.append("Resposta de correcao tambem ficou fora do contrato JSON aproveitavel.")
            return OllamaDetectionResult(
                entities=[],
                chunks_processed=1,
                json_rejected_chunks=json_rejected,
                correction_attempts=correction_attempts,
                correction_successes=correction_successes,
                json_rejection_reasons=rejection_reasons,
            )

    entities: list[Entity] = []
    preserved_items = 0
    for item in items:
        try:
            action = _normalize_action(item.get("action", "anonymize"))
            if action == "preserve":
                preserved_items += 1
                continue
            entity_text = str(item["text"]).strip()
            if not entity_text:
                continue
            start = int(item.get("start", 0))
            end = int(item.get("end", start + len(entity_text)))
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
                    confidence=_normalize_confidence(item.get("confidence")),
                    reason=_safe_reason(item.get("reason")),
                    action=action,
                )
            )
        except (KeyError, ValueError, TypeError):
            continue
    return OllamaDetectionResult(
        entities=entities,
        chunks_processed=1,
        json_rejected_chunks=json_rejected,
        correction_attempts=correction_attempts,
        correction_successes=correction_successes,
        json_rejection_reasons=rejection_reasons,
        preserved_items=preserved_items,
    )


def _request_ollama_generate(payload: dict) -> str:
    request = urllib.request.Request(
        f"{settings.ollama_url}/api/generate",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=settings.ollama_timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8")).get("response", "[]")
    except urllib.error.HTTPError as exc:
        raise OllamaDetectionError(f"modelo local indisponivel ou recusado pelo Ollama ({exc.code}).") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise OllamaDetectionError(
            f"Ollama local nao respondeu em ate {settings.ollama_timeout_seconds} segundos. "
            "Abra o Ollama, aguarde o modelo terminar de carregar e tente novamente."
        ) from exc
    except json.JSONDecodeError as exc:
        raise OllamaDetectionError("Ollama retornou resposta sem JSON valido.") from exc


def _correction_payload(raw_response: str, model: str) -> dict:
    clipped = raw_response[:6000]
    prompt = f"""{NO_THINK_PREFIX}
Converta a resposta abaixo para JSON valido e estrito conforme o contrato do ANON.
{json_contract_prompt()}
Use somente types permitidos. Se nao houver entidades aproveitaveis, responda exatamente {{"entities":[]}}.
Nao explique. Nao comente. Nao use Markdown.

RESPOSTA_ANTERIOR:
{clipped}
"""
    return {
        "model": model,
        "stream": False,
        "format": "json",
        "prompt": prompt,
        "think": False,
        "options": {"temperature": 0, "top_p": 0.9, "repeat_penalty": 1.1, "num_predict": 2048},
    }


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
        "PLACA": "VEHICLE_PLATE",
        "PLACA_VEICULO": "VEHICLE_PLATE",
        "CHASSI": "CHASSIS",
        "ENDERECO": "ADDRESS",
        "TELEFONE": "PHONE",
        "E-MAIL": "EMAIL",
        "PROCESSO": "PROCEEDING",
        "PROCEDIMENTO": "PROCEEDING",
        "PROTOCOLO": "PROTOCOL",
        "ORGAO": "ORGANIZATION",
        "INSTITUICAO": "ORGANIZATION",
    }
    normalized = aliases.get(normalized, normalized)
    blocked = {"VALUE", "AMOUNT", "MONEY", "DATE", "TIME", "PERCENTAGE", "HISTORY", "DESCRIPTION"}
    if normalized in blocked:
        return None
    try:
        return EntityType(normalized)
    except ValueError:
        return None


def _normalize_action(value: object) -> str:
    normalized = str(value or "anonymize").strip().lower()
    aliases = {
        "anonimizar": "anonymize",
        "substituir": "anonymize",
        "mask": "anonymize",
        "mascarar": "anonymize",
        "preservar": "preserve",
        "manter": "preserve",
        "reter": "preserve",
        "revisar": "review",
        "review_required": "review",
    }
    return aliases.get(normalized, normalized if normalized in {"anonymize", "preserve", "review"} else "anonymize")


def _normalize_confidence(value: object) -> float | None:
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        return None
    if confidence > 1 and confidence <= 100:
        confidence = confidence / 100
    if confidence < 0 or confidence > 1:
        return None
    return round(confidence, 3)


def _safe_reason(value: object) -> str | None:
    reason = " ".join(str(value or "").split())
    if not reason:
        return None
    return reason[:180]


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


def _load_entity_items(raw: str) -> list[dict]:
    cleaned = _strip_thinking(raw)
    candidates = [cleaned, *_json_substrings(cleaned)]
    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        items = _extract_entity_items(parsed)
        if items is not None:
            return items
    raise OllamaResponseFormatError(
        "modelo local respondeu, mas nao retornou JSON de entidades aproveitavel."
    )


def _extract_entity_items(value: object) -> list[dict] | None:
    if isinstance(value, list):
        normalized_items: list[dict] = []
        for item in value:
            if isinstance(item, dict):
                normalized_items.append(_normalize_item_keys(item))
        return normalized_items
    if isinstance(value, str):
        try:
            parsed = json.loads(_strip_thinking(value))
        except json.JSONDecodeError:
            return None
        return _extract_entity_items(parsed)
    if not isinstance(value, dict):
        return None
    if not value:
        return []
    normalized = _normalize_item_keys(value)
    if {"type", "text"}.issubset(normalized.keys()):
        return [normalized]
    category_items = _extract_category_map_items(value)
    if category_items:
        return category_items
    contract_items = _extract_contract_items(value)
    if contract_items is not None:
        return contract_items
    preferred_keys = (
        "entities",
        "entidades",
        "entidades_detectadas",
        "detected_entities",
        "detectedEntities",
        "items",
        "itens",
        "data",
        "dados",
        "result",
        "results",
        "resultado",
        "lista",
        "records",
        "registros",
        "response",
        "answer",
    )
    for key in preferred_keys:
        if key in value:
            items = _extract_entity_items(value[key])
            if items is not None:
                return items
    for nested in value.values():
        items = _extract_entity_items(nested)
        if items:
            return items
    return None


def _extract_contract_items(value: dict) -> list[dict] | None:
    entity_items: list[dict] = []
    found_contract_key = False
    for key in ("entities", "entidades", "detected_entities", "detectedEntities"):
        if key not in value:
            continue
        found_contract_key = True
        items = _extract_entity_items(value[key])
        if items:
            entity_items.extend(items)
    for key in ("preserve", "preservar", "preserved", "retencao", "retenção"):
        if key not in value:
            continue
        found_contract_key = True
        items = _extract_entity_items(value[key])
        if items:
            for item in items:
                item.setdefault("action", "preserve")
                item.setdefault("type", "OTHER_IDENTIFIER")
                entity_items.append(item)
    return entity_items if found_contract_key else None


def _extract_category_map_items(value: dict) -> list[dict]:
    items: list[dict] = []
    for key, entry in value.items():
        entity_type = _normalize_entity_type(str(key))
        if entity_type is None:
            continue
        if isinstance(entry, str):
            items.append({"type": entity_type.value, "text": entry})
            continue
        if isinstance(entry, list):
            for item in entry:
                if isinstance(item, str):
                    items.append({"type": entity_type.value, "text": item})
                elif isinstance(item, dict):
                    normalized = _normalize_item_keys(item)
                    normalized.setdefault("type", entity_type.value)
                    items.append(normalized)
    return items


def _normalize_item_keys(item: dict) -> dict:
    aliases = {
        "tipo": "type",
        "classe": "type",
        "categoria": "type",
        "entity_type": "type",
        "entityType": "type",
        "texto": "text",
        "valor": "text",
        "valor_original": "text",
        "original": "text",
        "entity": "text",
        "entidade": "text",
        "acao": "action",
        "ação": "action",
        "operacao": "action",
        "operação": "action",
        "motivo": "reason",
        "justificativa": "reason",
        "confianca": "confidence",
        "confiança": "confidence",
        "campo": "field",
        "coluna": "field",
        "fonte": "source_hint",
        "inicio": "start",
        "início": "start",
        "offset_start": "start",
        "start_index": "start",
        "fim": "end",
        "offset_end": "end",
        "end_index": "end",
    }
    normalized: dict = {}
    for key, value in item.items():
        normalized[aliases.get(str(key), str(key))] = value
    return normalized


def _json_substrings(value: str) -> list[str]:
    candidates: list[str] = []
    for open_char, close_char in (("[", "]"), ("{", "}")):
        start = value.find(open_char)
        end = value.rfind(close_char)
        if start >= 0 and end > start:
            candidates.append(value[start : end + 1].strip())
    return candidates
