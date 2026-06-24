import re

from app.models.schemas import DocumentKind, EntityType


PROFILE_PROMPTS: dict[DocumentKind, str] = {
    DocumentKind.rif: """
Perfil documental ativo: RIF / COAF.
Trate RIF como produto de inteligência financeira, inclusive exportações tabulares do Siscoaf e conjuntos relacionados de Comunicações, Envolvidos e Ocorrências.
Priorize contrapartes financeiras, pessoas comunicadas, comunicantes, envolvidos, empresas, CPF, CNPJ, contas, agências, chaves PIX, instituições financeiras, boletos, cartões, protocolos operacionais, idComunicacao, idOcorrencia, NumeroOcorrenciaBC e endereços.
Preserve integralmente valores monetários, datas, percentuais, quantidades, indicadores de atipicidade, classificações operacionais, tipoEnvolvido, bitPepCitado, bitPessoaObrigadaCitado, intServidorCitado, CodigoSegmento, natureza da operação financeira e termos como PIX, TED, DOC, saque, depósito, transferência, crédito, débito, fracionamento e análise financeira.
Se o documento for CSV ou tabela, preserve nomes de colunas, delimitadores, ordem das colunas, quantidade de linhas, quebras de linha e campos vazios; não converta CSV em Markdown, não alinhe colunas e não troque ponto e vírgula por vírgula.
Campos de alto risco em RIF/Siscoaf: informacoesAdicionais, Ocorrencia, cpfCnpjComunicante, nomeComunicante, cpfCnpjEnvolvido, nomeEnvolvido, agenciaEnvolvido, contaEnvolvido, NomeAgencia, NumeroAgencia, idComunicacao, idOcorrencia e NumeroOcorrenciaBC.
Não substitua a expressão técnica da operação; anonimize apenas a pessoa, empresa, conta, chave ou identificador vinculado.
""",
    DocumentKind.extrato_bancario: """
Perfil documental ativo: Extrato bancário.
Trate o documento como extrato bancário judicial, policial ou administrativo, detalhado ou consolidado, inclusive anexos como "Anexo B - Extrato Detalhado" e "Anexo C - Extrato Consolidado Por Depositantes/Beneficiários".
Priorize titular da conta, investigado, beneficiário, depositante, remetente, contraparte, CPF/CNPJ de titular ou contraparte, agência, conta, chaves bancárias, documentos de transação, protocolos de requisição e número de caso.
Preserve integralmente datas, valores em R$, percentuais, saldos, débitos, créditos, quantidade de movimentações, natureza da operação, histórico bancário, indicadores C/D, códigos de banco, nomes de instituições financeiras, nomes de colunas, número de página e avisos institucionais do extrato.
Preserve termos e padrões como Agência, Conta, Tipo Conta, Instituição, Débitos, Créditos, Abertura, Encerramento, Início Mov., Fim Mov., Identificados, CPF/CNPJ, Nome Benef/Depos, Nome do Depositante, Valor (R$), Qtd. Mov., Histórico, Doc., Observações, D/C, Total e Página.
A IA deve identificar somente entidades sensíveis. Não reescreva lançamentos, não interprete movimentações, não resuma, não altere ordem de linhas, não altere valores e não altere a classificação crédito/débito.
""",
    DocumentKind.inquerito: """
Perfil documental ativo: Inquérito policial.
Priorize investigados, vítimas, testemunhas, comunicantes, policiais, delegados, promotores, juízes, advogados, endereços, contatos, BO, IP, procedimentos, protocolos e documentos pessoais.
Preserve capitulação, narrativa técnica, datas, horários, valores, fundamentos legais, conclusões e determinações.
""",
    DocumentKind.relatorio: """
Perfil documental ativo: Relatório.
Priorize nomes de pessoas, empresas, unidades sensíveis, contatos, endereços, protocolos, placas, dados digitais e identificadores citados no corpo narrativo.
Preserve títulos, tópicos, conclusões, análise técnica, datas, valores, percentuais e enumerações.
""",
    DocumentKind.oficio: """
Perfil documental ativo: Ofício.
Priorize destinatários individualizados, remetentes individualizados, referências, protocolos, procedimentos, endereços, contatos, matrículas e dados funcionais.
Preserve assunto, vocativo institucional, fundamentos, requisições, prazos, datas e estrutura formal do expediente.
""",
    DocumentKind.administrativo: """
Perfil documental ativo: Documento administrativo.
Priorize SEI, protocolos, processos administrativos, matrículas funcionais, servidores, unidades específicas, assinaturas, contatos, endereços e identificadores cadastrais.
Preserve fundamentos administrativos, datas, prazos, despachos, determinações e estrutura tabular.
""",
    DocumentKind.auto: """
Perfil documental ativo: Automático.
Identifique o tipo documental pelo conteúdo e aplique a estratégia mais conservadora de anonimização, preservando valores, datas, fundamentação e análise técnica.
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
    DocumentKind.extrato_bancario: [
        (EntityType.bank_branch, re.compile(r"\bAg[êe]ncia\s*:\s*\d{1,6}(?:-\d)?\b", re.I)),
        (EntityType.bank_account, re.compile(r"\bConta\s*:\s*\d{3,14}(?:-\d)?\b", re.I)),
        (EntityType.other_identifier, re.compile(r"\bRequisi[çc][ãa]o\s*:\s*[\w./-]{1,30}\b", re.I)),
        (EntityType.other_identifier, re.compile(r"\bN[uú]mero\s+de\s+Caso\s*:\s*[\w./-]{1,30}\b", re.I)),
        (EntityType.cpf, re.compile(r"\bCPF/CNPJ\s*:\s*\d{10,11}\b", re.I)),
        (EntityType.cnpj, re.compile(r"\bCPF/CNPJ\s*:\s*\d{14}\b", re.I)),
        (EntityType.person, re.compile(r"\bTitular\s*:\s*([A-ZÁÉÍÓÚÂÊÔÃÕÇ][A-ZÁÉÍÓÚÂÊÔÃÕÇ '\.-]{5,120}?)(?=\s*\()", re.I)),
        (EntityType.other_identifier, re.compile(r"\b(?:Doc\.?|Documento)\s*[:\-]?\s*\d{5,18}\b", re.I)),
    ],
    DocumentKind.inquerito: [
        (EntityType.protocol, re.compile(r"\b(?:INQU[ÉE]RITO|IP|BO|B\.O\.|TCO|APFD)\s*(?:N[ºO.]*)?\s*[:\-]?\s*[\w./-]{3,}\b", re.I)),
        (EntityType.functional_id, re.compile(r"\b(?:MATR[ÍI]CULA|MF)\s*(?:FUNCIONAL)?\s*[:\-]?\s*\d{3,12}\b", re.I)),
    ],
    DocumentKind.relatorio: [
        (EntityType.protocol, re.compile(r"\b(?:RELAT[ÓO]RIO|PROTOCOLO|REFER[ÊE]NCIA)\s*(?:N[ºO.]*)?\s*[:\-]?\s*[\w./-]{4,}\b", re.I)),
    ],
    DocumentKind.oficio: [
        (EntityType.protocol, re.compile(r"\b(?:OF[ÍI]CIO|MEMORANDO|CIRCULAR)\s*(?:N[ºO.]*)?\s*[:\-]?\s*[\w./-]{3,}\b", re.I)),
        (EntityType.functional_id, re.compile(r"\b(?:MATR[ÍI]CULA|SIAPE|ID\s+FUNCIONAL)\s*[:\-]?\s*\d{3,12}\b", re.I)),
    ],
    DocumentKind.administrativo: [
        (EntityType.proceeding, re.compile(r"\bSEI\s*(?:N[ºO.]*)?\s*[:\-]?\s*[\d./-]{5,}\b", re.I)),
        (EntityType.protocol, re.compile(r"\b(?:PROCESSO\s+ADMINISTRATIVO|PROTOCOLO|PA)\s*(?:N[ºO.]*)?\s*[:\-]?\s*[\w./-]{4,}\b", re.I)),
        (EntityType.functional_id, re.compile(r"\b(?:MATR[ÍI]CULA|SIAPE|ID\s+FUNCIONAL)\s*[:\-]?\s*\d{3,12}\b", re.I)),
    ],
}


PROFILE_PROTECTED_PATTERNS: dict[DocumentKind, list[re.Pattern[str]]] = {
    DocumentKind.rif: [
        re.compile(r"\b(?:PIX|TED|DOC|SAQUE|DEP[ÓO]SITO|TRANSFER[ÊE]NCIA|CR[ÉE]DITO|D[ÉE]BITO|FRACIONAMENTO)\b", re.I),
    ],
    DocumentKind.extrato_bancario: [
        re.compile(r"\b(?:ANEXO\s+[BC]|EXTRATO|DETALHADO|CONSOLIDADO|AG[ÊE]NCIA|CONTA|TIPO\s+CONTA|INSTITUI[ÇC][ÃA]O)\b", re.I),
        re.compile(r"\b(?:D[ÉE]BITOS?|CR[ÉE]DITOS?|ABERTURA|ENCERRAMENTO|IN[ÍI]CIO\s+MOV|FIM\s+MOV|IDENTIFICADOS?)\b", re.I),
        re.compile(r"\b(?:VALOR\s*\(R\$\)|HIST[ÓO]RICO|OBSERVA[ÇC][ÕO]ES|QTD\.?\s+MOV|TOTAL|P[ÁA]GINA|D/C)\b", re.I),
        re.compile(r"\b(?:BANCO|BCO|CAIXA\s+ECONOMICA|SICOOB|S\.A\.|CONTA\s+CORRENTE|CONTA\s+POUPAN[ÇC]A)\b", re.I),
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
        re.compile(r"\b(?:Benefici[áa]rio|Remetente|Titular|Procurador|Representante Legal|S[óo]cio|Sacador|Respons[áa]vel|Depositante|Outros)\b", re.I),
        re.compile(r"\b(?:Sim|N[ãa]o|Serv\.?\s*Pub|-)\b", re.I),
    ],
    DocumentKind.extrato_bancario: [
        re.compile(r"\bR\$\s?\d{1,3}(?:\.\d{3})*,\d{2}\b"),
        re.compile(r"\b\d{1,2}/\d{1,2}/\d{2,4}\b"),
        re.compile(r"\b(?:D|C)\b"),
        re.compile(r"\b(?:Ag[êe]ncia|Conta|Tipo Conta|Institui[çc][ãa]o|D[ée]bitos|Cr[ée]ditos|Hist[óo]rico|Observa[çc][õo]es|Total)\b", re.I),
        re.compile(r"\b(?:SAQUE|DEP[ÓO]SITO|TRANSFER[ÊE]NCIA|CR[ÉE]DITO|D[ÉE]BITO|APLICA[ÇC][ÃA]O|RESGATE|TARIFA|PIX|TED|DOC)\b", re.I),
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
