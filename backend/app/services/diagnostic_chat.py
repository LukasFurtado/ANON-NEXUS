import json
import urllib.error
import urllib.request
from typing import Any

from app.core.config import settings
from app.core.profile_loader import load_profile, ProfileNotFoundError
from app.core.safe_summary import load_safe_summary


def answer_diagnostic_question(payload: dict[str, Any]) -> dict[str, str]:
    question = str(payload.get("question") or "").strip()
    profile_id = str(payload.get("profile") or "").strip()
    document_id = str(payload.get("document_id") or "").strip()
    if not question:
        return {"source": "anon", "answer": _fallback_answer(question)}

    try:
        return {"source": "ollama", "answer": _ask_nexus_ai(question, profile_id, document_id)}
    except Exception:
        return {"source": "anon", "answer": _fallback_answer(question)}


def _ask_nexus_ai(question: str, profile_id: str, document_id: str) -> str:
    context = _safe_context(profile_id, document_id)
    prompt = f"""
Você é a IA NEXUS, assistente institucional do ANON.

Sua função é orientar o operador sobre:
- finalidade do ANON;
- características do produto anonimizado;
- revisão humana obrigatória;
- preservação de valores, datas, estrutura, tabelas, fundamentos e conclusões;
- cuidados com RIF/COAF, extratos bancários e relatórios investigativos;
- condutas gerais quando algo não sair como esperado.

Regras obrigatórias:
- Responda em português do Brasil.
- Seja objetiva, institucional e útil.
- Não cite nomes de arquivos, caminhos, rotas, código, JSON, backend, eventos internos, logs internos ou estrutura interna do sistema.
- Não afirme que analisou conteúdo do documento.
- Não dê diagnóstico técnico de falhas internas.
- Quando o operador mencionar erro, problema, falha ou dúvida sobre resultado, recomende: revisar manualmente, conferir o produto final antes de uso externo, tentar novo processamento se necessário, confirmar que o Ollama e o modelo local estejam disponíveis, e encaminhar para suporte/auditoria institucional se persistir.
- Sempre lembre que a revisão humana é imprescindível antes de compartilhar, juntar, imprimir, remeter ou usar oficialmente.

CONTEXTO SEGURO DISPONIVEL:
{context}

PERGUNTA DO OPERADOR:
{question}
"""
    request = urllib.request.Request(
        f"{settings.ollama_url}/api/generate",
        data=json.dumps(
            {
                "model": settings.nexus_assistant_model,
                "stream": False,
                "prompt": prompt,
                "think": False,
                "options": {"temperature": 0.1},
            }
        ).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=min(settings.ollama_timeout_seconds, 120)) as response:
        answer = json.loads(response.read().decode("utf-8")).get("response", "").strip()
        return answer or _fallback_answer(question)


def _safe_context(profile_id: str, document_id: str) -> str:
    lines: list[str] = []
    if profile_id:
        try:
            profile = load_profile(profile_id)
            lines.extend(
                [
                    f"Perfil: {profile.get('display_name', profile_id)}",
                    f"Preservar: {', '.join(profile.get('preserve_always', []))}",
                    f"Anonimizar: {', '.join(profile.get('anonymize_always', []))}",
                    f"Ambiguidade: {profile.get('ambiguity_resolution', 'conservador')}",
                ]
            )
        except ProfileNotFoundError:
            lines.append(f"Perfil informado indisponivel: {profile_id}")
    if document_id:
        summary = load_safe_summary(document_id)
        if summary:
            lines.extend(
                [
                    f"Resumo seguro: status={summary.get('quality_status', 'nao informado')}, score={summary.get('quality_score', 'nao informado')}",
                    f"Entidades detectadas: {summary.get('total_entities_detected', 0)}",
                    f"Tipos de entidade: {summary.get('entities_by_type', {})}",
                    f"Avisos seguros: {summary.get('warnings_raised', [])}",
                ]
            )
    return "\n".join(lines) if lines else "Sem resumo seguro especifico. Responder apenas com orientacao geral do ANON."


def _fallback_answer(question: str) -> str:
    normalized = question.lower()

    if any(term in normalized for term in ("erro", "problema", "falha", "não deu", "nao deu", "travou")):
        return (
            "Se algo não sair como esperado, trate o produto como preliminar: revise manualmente o documento, "
            "confira se os identificadores sensíveis foram substituídos, tente novo processamento quando necessário "
            "e confirme se o Ollama e o modelo local estão disponíveis. Se a inconsistência persistir, encaminhe para suporte ou auditoria institucional."
        )

    if any(term in normalized for term in ("rif", "coaf", "financeir", "movimenta")):
        return (
            "Em RIF e dados financeiros, o ANON deve preservar valores, datas, movimentações, ordem das informações "
            "e coerência analítica, substituindo apenas dados capazes de identificar pessoas físicas, jurídicas ou vínculos sensíveis."
        )

    if any(term in normalized for term in ("extrato", "banc", "conta")):
        return (
            "Em extratos bancários, a revisão deve confirmar se lançamentos, datas, valores, saldos e estrutura visual foram preservados. "
            "A anonimização deve recair sobre identificadores sensíveis, como nomes, documentos, contas, chaves e demais vínculos identificáveis."
        )

    if any(term in normalized for term in ("produto", "resultado", "funcionamento", "caracter")):
        return (
            "O produto do ANON deve manter o documento compreensível e fiel ao original, alterando somente identificadores sensíveis. "
            "A saída deve permitir conferência, rastreabilidade e revisão humana antes de qualquer uso oficial."
        )

    if any(term in normalized for term in ("revis", "confer", "valid", "compartilh")):
        return (
            "A revisão humana é obrigatória. Antes de compartilhar, verifique nomes, documentos, endereços, contatos, contas, chaves de pagamento, "
            "empresas e demais identificadores, garantindo que valores, datas, tabelas, fundamentos e conclusões não tenham sido alterados indevidamente."
        )

    if any(term in normalized for term in ("sigilo", "seguran", "interno", "uso")):
        return (
            "O uso do ANON deve permanecer institucional, local e controlado. O operador deve observar sigilo, finalidade, necessidade, "
            "rastreabilidade e responsabilidade funcional sobre o produto final."
        )

    return (
        "A IA NEXUS está vinculada ao modelo local configurado para orientar o uso do ANON. "
        "Posso explicar finalidade, características do produto anonimizado, cuidados por perfil documental e medidas de revisão manual obrigatória."
    )
