import re

from app.models.schemas import DocumentKind, EntityType


PROFILE_PROMPTS: dict[DocumentKind, str] = {
    DocumentKind.rif: """
Perfil documental ativo: RIF / COAF.
Trate RIF como produto de inteligencia financeira, inclusive exportacoes tabulares do Siscoaf e conjuntos relacionados de Comunicacoes, Envolvidos e Ocorrencias.
Priorize contrapartes financeiras, pessoas comunicadas, comunicantes, envolvidos, empresas, CPF, CNPJ, contas, agencias, chaves PIX, instituicoes financeiras, boletos, cartoes, protocolos operacionais, idComunicacao, idOcorrencia, NumeroOcorrenciaBC e enderecos.
Preserve integralmente valores monetarios, datas, percentuais, quantidades, indicadores de atipicidade, classificacoes operacionais, tipoEnvolvido, bitPepCitado, bitPessoaObrigadaCitado, intServidorCitado, CodigoSegmento, natureza da operacao financeira e termos como PIX, TED, DOC, saque, deposito, transferencia, credito, debito, fracionamento e analise financeira.
Se o documento for CSV ou tabela, preserve nomes de colunas, delimitadores, ordem das colunas, quantidade de linhas, quebras de linha e campos vazios; nao converta CSV em Markdown, nao alinhe colunas e nao troque ponto e virgula por virgula.
Campos de alto risco em RIF/Siscoaf: informacoesAdicionais, Ocorrencia, cpfCnpjComunicante, nomeComunicante, cpfCnpjEnvolvido, nomeEnvolvido, agenciaEnvolvido, contaEnvolvido, NomeAgencia, NumeroAgencia, idComunicacao, idOcorrencia e NumeroOcorrenciaBC.
Indexador deve ser preservado quando for chave relacional sem capacidade identificadora; se for chave composta sensivel ou identificar caso concreto, anonimizar de forma consistente.
Nao substitua a expressao tecnica da operacao; anonimize apenas a pessoa, empresa, conta, chave ou identificador vinculado.
""",
    DocumentKind.inquerito: """
Perfil documental ativo: Inquerito policial.
Priorize investigados, vitimas, testemunhas, comunicantes, policiais, delegados, promotores, juizes, advogados, enderecos, contatos, BO, IP, procedimentos, protocolos e documentos pessoais.
Preserve capitulacao, narrativa tecnica, datas, horarios, valores, fundamentos legais, conclusoes e determinacoes.
""",
    DocumentKind.relatorio: """
Perfil documental ativo: Relatorio.
Priorize nomes de pessoas, empresas, unidades sensiveis, contatos, enderecos, protocolos, placas, dados digitais e identificadores citados no corpo narrativo.
Preserve titulos, topicos, conclusoes, analise tecnica, datas, valores, percentuais e enumeracoes.
""",
    DocumentKind.oficio: """
Perfil documental ativo: Oficio.
Priorize destinatarios individualizados, remetentes individualizados, referencias, protocolos, procedimentos, enderecos, contatos, matriculas e dados funcionais.
Preserve assunto, vocativo institucional, fundamentos, requisicoes, prazos, datas e estrutura formal do expediente.
""",
    DocumentKind.administrativo: """
Perfil documental ativo: Documento administrativo.
Priorize SEI, protocolos, processos administrativos, matriculas funcionais, servidores, unidades especificas, assinaturas, contatos, enderecos e identificadores cadastrais.
Preserve fundamentos administrativos, datas, prazos, despachos, determinacoes e estrutura tabular.
""",
    DocumentKind.auto: """
Perfil documental ativo: Automatico.
Identifique o tipo documental pelo conteudo e aplique a estrategia mais conservadora de anonimização, preservando valores, datas, fundamentacao e analise tecnica.
""",
}


PROFILE_REGEX_PATTERNS: dict[DocumentKind, list[tuple[EntityType, re.Pattern[str]]]] = {
    DocumentKind.rif: [
        (EntityType.bank_branch, re.compile(r"\b(?:AG[ÊE]NCIA|AG\.?)\s*(?:N[ºO.]*)?\s*[:\-]?\s*\d{3,5}(?:-\d)?\b", re.I)),
        (EntityType.bank_account, re.compile(r"\b(?:CONTA\s+(?:CORRENTE|POUPAN[ÇC]A)?|C/C|CC)\s*(?:N[ºO.]*)?\s*[:\-]?\s*\d{3,14}(?:-\d)?\b", re.I)),
        (EntityType.pix, re.compile(r"\b(?:CHAVE\s+PIX|PIX)\s*(?:CPF|CNPJ|E-?MAIL|TELEFONE|ALEAT[ÓO]RIA|EVP)?\s*[:\-]\s*[\w.@+\-/]{5,}\b", re.I)),
        (EntityType.boleto, re.compile(r"\b(?:\d{5}\.?\d{5}\s?){3,5}\d{1,14}\b")),
        (EntityType.protocol, re.compile(r"\b(?:idComunicacao|idOcorrencia|NumeroOcorrenciaBC)\s*[:\-]\s*[\w./-]{3,}\b", re.I)),
        (EntityType.cpf, re.compile(r"\bcpfCnpj(?:Comunicante|Envolvido)\s*[:\-]\s*\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b", re.I)),
        (EntityType.cnpj, re.compile(r"\bcpfCnpj(?:Comunicante|Envolvido)\s*[:\-]\s*\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}\b", re.I)),
        (EntityType.bank_branch, re.compile(r"\b(?:agenciaEnvolvido|NumeroAgencia|NomeAgencia)\s*[:\-]\s*[\w ./'-]{2,60}\b", re.I)),
        (EntityType.bank_account, re.compile(r"\bcontaEnvolvido\s*[:\-]\s*[\w./-]{3,30}\b", re.I)),
    ],
    DocumentKind.inquerito: [
        (EntityType.protocol, re.compile(r"\b(?:INQU[ÉE]RITO|IP|BO|B\.O\.|TCO|APFD)\s*(?:N[ºO.]*)?\s*[:\-]?\s*[\w./-]{3,}\b", re.I)),
        (EntityType.functional_id, re.compile(r"\b(?:MATR[IÍ]CULA|MF)\s*(?:FUNCIONAL)?\s*[:\-]?\s*\d{3,12}\b", re.I)),
    ],
    DocumentKind.relatorio: [
        (EntityType.protocol, re.compile(r"\b(?:RELAT[ÓO]RIO|PROTOCOLO|REFER[ÊE]NCIA)\s*(?:N[ºO.]*)?\s*[:\-]?\s*[\w./-]{4,}\b", re.I)),
    ],
    DocumentKind.oficio: [
        (EntityType.protocol, re.compile(r"\b(?:OF[ÍI]CIO|MEMORANDO|CIRCULAR)\s*(?:N[ºO.]*)?\s*[:\-]?\s*[\w./-]{3,}\b", re.I)),
        (EntityType.functional_id, re.compile(r"\b(?:MATR[IÍ]CULA|SIAPE|ID\s+FUNCIONAL)\s*[:\-]?\s*\d{3,12}\b", re.I)),
    ],
    DocumentKind.administrativo: [
        (EntityType.proceeding, re.compile(r"\bSEI\s*(?:N[ºO.]*)?\s*[:\-]?\s*[\d./-]{5,}\b", re.I)),
        (EntityType.protocol, re.compile(r"\b(?:PROCESSO\s+ADMINISTRATIVO|PROTOCOLO|PA)\s*(?:N[ºO.]*)?\s*[:\-]?\s*[\w./-]{4,}\b", re.I)),
        (EntityType.functional_id, re.compile(r"\b(?:MATR[IÍ]CULA|SIAPE|ID\s+FUNCIONAL)\s*[:\-]?\s*\d{3,12}\b", re.I)),
    ],
}


PROFILE_PROTECTED_PATTERNS: dict[DocumentKind, list[re.Pattern[str]]] = {
    DocumentKind.rif: [
        re.compile(r"\b(?:PIX|TED|DOC|SAQUE|DEP[ÓO]SITO|TRANSFER[ÊE]NCIA|CR[ÉE]DITO|D[ÉE]BITO|FRACIONAMENTO)\b", re.I),
    ],
    DocumentKind.inquerito: [
        re.compile(r"\b(?:ART\.?|ARTIGO|LEI|C[ÓO]DIGO\s+PENAL|CPP|CONSTITUI[ÇC][ÃA]O)\b", re.I),
    ],
    DocumentKind.oficio: [
        re.compile(r"\b(?:ASSUNTO|REFER[ÊE]NCIA|PRAZO|REQUISI[ÇC][ÃA]O|ENCAMINHAMENTO)\b", re.I),
    ],
    DocumentKind.administrativo: [
        re.compile(r"\b(?:DESPACHO|PORTARIA|PRAZO|PUBLICA[ÇC][ÃA]O|D.O.)\b", re.I),
    ],
}


PROFILE_OUTPUT_TERMS: dict[DocumentKind, list[re.Pattern[str]]] = {
    DocumentKind.rif: [
        re.compile(r"\bPIX\b", re.I),
        re.compile(r"\b(?:TED|DOC)\b", re.I),
        re.compile(r"\bR\$\s?\d{1,3}(?:\.\d{3})*,\d{2}\b"),
        re.compile(r"\b(?:Beneficiario|Beneficiário|Remetente|Titular|Procurador|Representante Legal|Socio|Sócio|Sacador|Responsavel|Responsável|Depositante|Outros)\b", re.I),
        re.compile(r"\b(?:Sim|Nao|Não|Serv\.?\s*Pub|-)\b", re.I),
    ],
    DocumentKind.inquerito: [
        re.compile(r"\b(?:art\.|artigo|lei)\b", re.I),
    ],
}


def profile_prompt(document_kind: DocumentKind) -> str:
    return PROFILE_PROMPTS.get(document_kind, PROFILE_PROMPTS[DocumentKind.auto]).strip()


def profile_regex_patterns(document_kind: DocumentKind) -> list[tuple[EntityType, re.Pattern[str]]]:
    return PROFILE_REGEX_PATTERNS.get(document_kind, [])


def profile_protected_patterns(document_kind: DocumentKind) -> list[re.Pattern[str]]:
    return PROFILE_PROTECTED_PATTERNS.get(document_kind, [])


def profile_output_terms(document_kind: DocumentKind) -> list[re.Pattern[str]]:
    return PROFILE_OUTPUT_TERMS.get(document_kind, [])
