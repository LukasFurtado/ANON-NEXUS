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
Nao substitua a expressao tecnica da operacao; anonimize apenas a pessoa, empresa, conta, chave ou identificador vinculado.
""",
    DocumentKind.extrato_bancario: """
Perfil documental ativo: Extrato bancario.
Trate o documento como extrato bancario judicial, policial ou administrativo, detalhado ou consolidado, inclusive arquivos DELOS.
Priorize titular da conta, investigado, beneficiario, depositante, remetente, contraparte, CPF/CNPJ de titular ou contraparte e chaves bancarias do titular.
Preserve integralmente datas, valores em R$, percentuais, saldos, debitos, creditos, quantidade de movimentacoes, natureza da operacao, historico bancario, indicadores D/C, codigos de banco, nomes de instituicoes financeiras, nomes de colunas, numero de pagina e avisos institucionais do extrato.
Em extratos DELOS, preserve SEMPRE a coluna Doc., os identificadores Requisicao e Numero de Caso, a coluna Inst., codigos ISPB/COMPE e termos operacionais como COMPRA COM CARTAO, JUROS, DEPOSITO ONLINE, PAGAMENTO CONTA, PAGTO CARTAO CREDITO, SAQUE, TARIFA, TED, DOC, TRANSFERENCIA e similares.
Anonimize o titular extraido do cabecalho em todas as ocorrencias posteriores, inclusive em Nome Benef/Depos, Observacoes, padrao "POR [NOME]" e variacoes eleitorais ou abreviadas.
A IA deve identificar somente entidades sensiveis. Nao reescreva lancamentos, nao interprete movimentacoes, nao resuma, nao altere ordem de linhas, nao altere valores e nao altere a classificacao credito/debito.
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
Identifique o tipo documental pelo conteudo e aplique a estrategia mais conservadora de anonimizacao, preservando valores, datas, fundamentacao e analise tecnica.
""",
}


PROFILE_REGEX_PATTERNS: dict[DocumentKind, list[tuple[EntityType, re.Pattern[str]]]] = {
    DocumentKind.rif: [
        (EntityType.bank_branch, re.compile(r"\b(?:AGENCIA|AG\.?)\s*(?:N[O.]*)?\s*[:\-]?\s*\d{3,5}(?:-\d)?\b", re.I)),
        (EntityType.bank_account, re.compile(r"\b(?:CONTA\s+(?:CORRENTE|POUPANCA)?|C/C|CC)\s*(?:N[O.]*)?\s*[:\-]?\s*\d{3,14}(?:-\d)?\b", re.I)),
        (EntityType.pix, re.compile(r"\b(?:CHAVE\s+PIX|PIX)\s*(?:CPF|CNPJ|E-?MAIL|TELEFONE|ALEATORIA|EVP)?\s*[:\-]\s*[\w.@+\-/]{5,}\b", re.I)),
        (EntityType.boleto, re.compile(r"\b(?:\d{5}\.?\d{5}\s?){3,5}\d{1,14}\b")),
        (EntityType.protocol, re.compile(r"\b(?:idComunicacao|idOcorrencia|NumeroOcorrenciaBC)\s*[:\-]\s*[\w./-]{3,}\b", re.I)),
        (EntityType.cpf, re.compile(r"\bcpfCnpj(?:Comunicante|Envolvido)\s*[:\-]\s*\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b", re.I)),
        (EntityType.cnpj, re.compile(r"\bcpfCnpj(?:Comunicante|Envolvido)\s*[:\-]\s*\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}\b", re.I)),
        (EntityType.bank_branch, re.compile(r"\b(?:agenciaEnvolvido|NumeroAgencia|NomeAgencia)\s*[:\-]\s*[\w ./'-]{2,60}\b", re.I)),
        (EntityType.bank_account, re.compile(r"\bcontaEnvolvido\s*[:\-]\s*[\w./-]{3,30}\b", re.I)),
    ],
    DocumentKind.extrato_bancario: [
        (EntityType.bank_branch, re.compile(r"\bAgencia\s*:\s*\d{1,6}(?:-\d)?\b", re.I)),
        (EntityType.bank_account, re.compile(r"\bConta\s*:\s*\d{3,14}(?:-\d)?\b", re.I)),
        (EntityType.cpf, re.compile(r"\bCPF/CNPJ\s*:\s*\d{10,11}\b", re.I)),
        (EntityType.cnpj, re.compile(r"\bCPF/CNPJ\s*:\s*\d{14}\b", re.I)),
        (EntityType.person, re.compile(r"\bTitular\s*:\s*([A-ZÀ-ÖØ-Ý][A-ZÀ-ÖØ-Ý '\.-]{5,120}?)(?=\s*\()", re.I)),
    ],
    DocumentKind.inquerito: [
        (EntityType.protocol, re.compile(r"\b(?:INQUERITO|IP|BO|B\.O\.|TCO|APFD)\s*(?:N[O.]*)?\s*[:\-]?\s*[\w./-]{3,}\b", re.I)),
        (EntityType.functional_id, re.compile(r"\b(?:MATRICULA|MF)\s*(?:FUNCIONAL)?\s*[:\-]?\s*\d{3,12}\b", re.I)),
    ],
    DocumentKind.relatorio: [
        (EntityType.protocol, re.compile(r"\b(?:RELATORIO|PROTOCOLO|REFERENCIA)\s*(?:N[O.]*)?\s*[:\-]?\s*[\w./-]{4,}\b", re.I)),
    ],
    DocumentKind.oficio: [
        (EntityType.protocol, re.compile(r"\b(?:OFICIO|MEMORANDO|CIRCULAR)\s*(?:N[O.]*)?\s*[:\-]?\s*[\w./-]{3,}\b", re.I)),
        (EntityType.functional_id, re.compile(r"\b(?:MATRICULA|SIAPE|ID\s+FUNCIONAL)\s*[:\-]?\s*\d{3,12}\b", re.I)),
    ],
    DocumentKind.administrativo: [
        (EntityType.proceeding, re.compile(r"\bSEI\s*(?:N[O.]*)?\s*[:\-]?\s*[\d./-]{5,}\b", re.I)),
        (EntityType.protocol, re.compile(r"\b(?:PROCESSO\s+ADMINISTRATIVO|PROTOCOLO|PA)\s*(?:N[O.]*)?\s*[:\-]?\s*[\w./-]{4,}\b", re.I)),
        (EntityType.functional_id, re.compile(r"\b(?:MATRICULA|SIAPE|ID\s+FUNCIONAL)\s*[:\-]?\s*\d{3,12}\b", re.I)),
    ],
}


PROFILE_PROTECTED_PATTERNS: dict[DocumentKind, list[re.Pattern[str]]] = {
    DocumentKind.rif: [
        re.compile(r"\b(?:PIX|TED|DOC|SAQUE|DEPOSITO|TRANSFERENCIA|CREDITO|DEBITO|FRACIONAMENTO)\b", re.I),
    ],
    DocumentKind.extrato_bancario: [
        re.compile(r"\b(?:ANEXO\s+[BC]|EXTRATO|DETALHADO|CONSOLIDADO|AGENCIA|CONTA|TIPO\s+CONTA|INSTITUICAO)\b", re.I),
        re.compile(r"\b(?:DEBITOS?|CREDITOS?|ABERTURA|ENCERRAMENTO|INICIO\s+MOV|FIM\s+MOV|IDENTIFICADOS?)\b", re.I),
        re.compile(r"\b(?:VALOR\s*\(R\$\)|HISTORICO|OBSERVACOES|QTD\.?\s+MOV|TOTAL|PAGINA|D/C)\b", re.I),
        re.compile(r"\b(?:BANCO|BCO|CAIXA\s+ECONOMICA|SICOOB|S\.A\.|CONTA\s+CORRENTE|CONTA\s+POUPANCA)\b", re.I),
    ],
    DocumentKind.inquerito: [
        re.compile(r"\b(?:ART\.?|ARTIGO|LEI|CODIGO\s+PENAL|CPP|CONSTITUICAO)\b", re.I),
    ],
    DocumentKind.oficio: [
        re.compile(r"\b(?:ASSUNTO|REFERENCIA|PRAZO|REQUISICAO|ENCAMINHAMENTO)\b", re.I),
    ],
    DocumentKind.administrativo: [
        re.compile(r"\b(?:DESPACHO|PORTARIA|PRAZO|PUBLICACAO|D.O.)\b", re.I),
    ],
}


PROFILE_OUTPUT_TERMS: dict[DocumentKind, list[re.Pattern[str]]] = {
    DocumentKind.rif: [
        re.compile(r"\bPIX\b", re.I),
        re.compile(r"\b(?:TED|DOC)\b", re.I),
        re.compile(r"\bR\$\s?\d{1,3}(?:\.\d{3})*,\d{2}\b"),
        re.compile(r"\b(?:Beneficiario|Remetente|Titular|Procurador|Representante Legal|Socio|Sacador|Responsavel|Depositante|Outros)\b", re.I),
        re.compile(r"\b(?:Sim|Nao|Serv\.?\s*Pub|-)\b", re.I),
    ],
    DocumentKind.extrato_bancario: [
        re.compile(r"\bR\$\s?\d{1,3}(?:\.\d{3})*,\d{2}\b"),
        re.compile(r"\b\d{1,2}/\d{1,2}/\d{2,4}\b"),
        re.compile(r"\b(?:D|C)\b"),
        re.compile(r"\b(?:Agencia|Conta|Tipo Conta|Instituicao|Debitos|Creditos|Historico|Observacoes|Total)\b", re.I),
        re.compile(r"\b(?:SAQUE|DEPOSITO|TRANSFERENCIA|CREDITO|DEBITO|APLICACAO|RESGATE|TARIFA|PIX|TED|DOC)\b", re.I),
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

