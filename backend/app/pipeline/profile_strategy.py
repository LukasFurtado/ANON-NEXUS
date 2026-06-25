import re

from app.models.schemas import DocumentKind, EntityType


PROFILE_PROMPTS: dict[DocumentKind, str] = {
    DocumentKind.rif: """
Perfil documental ativo: RIF / COAF.
Trate RIF como produto de inteligencia financeira, inclusive exportacoes tabulares do Siscoaf e conjuntos relacionados de Comunicacoes, Envolvidos e Ocorrencias.
Reconheca os modelos RIF[numeros]_Envolvidos.csv, RIF[numeros]_Ocorrencias.csv e RIF[numeros]_Comunicacoes.csv. O campo Indexador e a chave relacional entre arquivos e deve ser preservado.
Em Envolvidos, anonimizar cpfCnpjEnvolvido, nomeEnvolvido, agenciaEnvolvido e contaEnvolvido quando preenchidos. Preservar tipoEnvolvido, DataAberturaConta, DataAtualizacaoConta, bitPepCitado, bitPessoaObrigadaCitado e intServidorCitado.
Em Ocorrencias, preservar idOcorrencia e Ocorrencia, pois descrevem classificacoes, tipologias ou codigos operacionais. So sinalize entidade sensivel se houver dado pessoal acidental dentro do texto livre.
Em Comunicacoes, preservar idComunicacao, NumeroOcorrenciaBC, datas, cpfCnpjComunicante, nomeComunicante, CidadeAgencia, UFAgencia, NomeAgencia, NumeroAgencia, CampoA, CampoB, CampoC, CampoD, CampoE e CodigoSegmento. No campo informacoesAdicionais, anonimizar apenas pessoas, empresas privadas sensiveis, CPF/CNPJ de contraparte, contas, agencias, PIX, enderecos, telefones e emails.
Preserve integralmente valores monetarios, datas, percentuais, quantidades, indicadores de atipicidade, classificacoes operacionais, CodigoSegmento, natureza da operacao financeira e termos como PIX, TED, DOC, saque, deposito, transferencia, credito, debito, fracionamento e analise financeira.
Se o documento for CSV ou tabela, preserve nomes de colunas, delimitadores, ordem das colunas, quantidade de linhas, quebras de linha e campos vazios; nao converta CSV em Markdown, nao alinhe colunas e nao troque ponto e virgula por virgula.
Nao substitua a expressao tecnica da operacao; anonimize apenas a pessoa, empresa, conta, chave ou identificador vinculado.
""",
    DocumentKind.extrato_bancario: """
Perfil documental ativo: Extrato bancario.
Trate o documento como extrato bancario judicial, policial ou administrativo, detalhado ou consolidado, inclusive arquivos DELOS.
Priorize titular da conta, investigado, beneficiario, depositante, remetente, contraparte, CPF/CNPJ de titular ou contraparte e chaves bancarias do titular.
Preserve integralmente datas, valores em R$, percentuais, saldos, debitos, creditos, quantidade de movimentacoes, natureza da operacao, historico bancario, indicadores D/C, codigos de banco, nomes de instituicoes financeiras, nomes de colunas, numero de pagina e avisos institucionais do extrato.
Em extratos DELOS, preserve SEMPRE a coluna Doc., os identificadores Requisicao e Numero de Caso, a coluna Inst., codigos ISPB/COMPE e termos operacionais como COMPRA COM CARTAO, JUROS, DEPOSITO ONLINE, PAGAMENTO CONTA, PAGTO CARTAO CREDITO, SAQUE, TARIFA, TED, DOC, TRANSFERENCIA e similares.
Use a engenharia reversa DELOS: Data, Historico, Doc., Valor, D/C, Inst., Ag, Conta e Observacoes sao colunas com semantica propria. A coluna Doc. pode conter 0 ou numeros de operacao; isso deve ser preservado. A coluna CPF/CNPJ e Nome Benef/Depos sao sensiveis quando identificam titular, beneficiario, depositante, remetente ou contraparte.
Flags como DOCUMENTO EXIGE RECUPERACAO MANUAL, PESQUISA CONCLUIDA, PORTADORES DE NUMERARIOS INFERIORES A DEZ MIL REAIS NAO SAO IDENTIFICADOS, encerramento 31/12/9999 e Doc. 0 sao informacoes tecnicas do extrato e nao devem ser anonimizadas.
Anonimize o titular extraido do cabecalho em todas as ocorrencias posteriores, inclusive em Nome Benef/Depos, Observacoes, padrao "POR [NOME]" e variacoes eleitorais ou abreviadas.
A IA deve identificar somente entidades sensiveis. Nao reescreva lancamentos, nao interprete movimentacoes, nao resuma, nao altere ordem de linhas, nao altere valores e nao altere a classificacao credito/debito.
""",
    DocumentKind.relatorio_investigativo: """
Perfil documental ativo: Relatorio investigativo.
Trate o documento como relatorio investigativo policial, ministerial, administrativo ou de controle, em PDF ou DOCX, com foco exclusivo em desidentificacao.
Preserve integralmente a estrutura textual, ordem de paragrafos, numeracao, tabelas, cabecalhos, rodapes, titulos, fundamentos, analise tecnica, conclusoes, valores, datas, horarios, percentuais, referencias a folhas, numeros de IP, BO, processo, SEI, relatorio, oficio, portaria e demais referencias procedimentais.
Preserve nomes de orgaos publicos, unidades policiais, delegacias, ministerios, tribunais, bancos, plataformas digitais citadas como fonte de dados, municipios, estados, marcas/modelos de veiculos, tipificacoes penais, artigos de lei, jurisprudencia, IMEI, ERB e referencias tecnicas que nao identifiquem diretamente pessoa fisica ou juridica privada investigada.
Anonimize nomes de pessoas fisicas, investigados, vitimas, testemunhas, comunicantes, autoridades assinantes ou individualizadas, peritos, servidores identificaveis, matriculas funcionais, CPF, RG, CNH, passaporte, CNPJ de empresas privadas investigadas, telefones, e-mails, enderecos completos, CEP, contas bancarias, agencias quando vinculadas ao titular investigado, chaves PIX, placas, usuarios/perfis de redes sociais, IPs individuais e qualquer identificador pessoal.
Quando o papel estiver claro, prefira marcadores semanticamente uteis como [INVESTIGADO_001], [VITIMA_001], [TESTEMUNHA_001] ou [AUTORIDADE_001]. Quando o papel for ambiguo, use [PESSOA_001]. Mantenha o mesmo identificador para a mesma entidade em todo o documento e em todo o conjunto processado.
Em citacoes, transcricoes, tabelas e documentos reproduzidos dentro do relatorio, anonimize apenas os dados pessoais internos e preserve o texto tecnico ao redor. Nao resuma, nao reescreva, nao interprete e nao crie nova narrativa.
""",
    DocumentKind.personalizado: """
Perfil documental ativo: Personalizado.
Trate o documento como caso atipico que sera finalizado por revisao dirigida do operador.
Preserve integralmente texto, estrutura, valores, datas, tabelas, titulos e ordem das informacoes.
Somente os termos definidos pelo operador devem ser substituidos na etapa de finalizacao manual.
""",
}


PROFILE_REGEX_PATTERNS: dict[DocumentKind, list[tuple[EntityType, re.Pattern[str]]]] = {
    DocumentKind.rif: [
        (EntityType.bank_branch, re.compile(r"\b(?:AGENCIA|AG\.?)\s*(?:N[O.]*)?\s*[:\-]?\s*\d{3,5}(?:-\d)?\b", re.I)),
        (EntityType.bank_account, re.compile(r"\b(?:CONTA\s+(?:CORRENTE|POUPANCA)?|C/C|CC)\s*(?:N[O.]*)?\s*[:\-]?\s*\d{3,14}(?:-\d)?\b", re.I)),
        (EntityType.pix, re.compile(r"\b(?:CHAVE\s+PIX|PIX)\s*(?:CPF|CNPJ|E-?MAIL|TELEFONE|ALEATORIA|EVP)?\s*[:\-]\s*[\w.@+\-/]{5,}\b", re.I)),
        (EntityType.boleto, re.compile(r"\b(?:\d{5}\.?\d{5}\s?){3,5}\d{1,14}\b")),
        (EntityType.cpf, re.compile(r"\bcpfCnpj(?:Comunicante|Envolvido)\s*[:\-]\s*\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b", re.I)),
        (EntityType.cnpj, re.compile(r"\bcpfCnpj(?:Comunicante|Envolvido)\s*[:\-]\s*\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}\b", re.I)),
        (EntityType.bank_branch, re.compile(r"\bagenciaEnvolvido\s*[:\-]\s*[\w ./'-]{2,60}\b", re.I)),
        (EntityType.bank_account, re.compile(r"\bcontaEnvolvido\s*[:\-]\s*[\w./-]{3,30}\b", re.I)),
    ],
    DocumentKind.extrato_bancario: [
        (EntityType.bank_branch, re.compile(r"\bAgencia\s*:\s*\d{1,6}(?:-\d)?\b", re.I)),
        (EntityType.bank_account, re.compile(r"\bConta\s*:\s*\d{3,14}(?:-\d)?\b", re.I)),
        (EntityType.cpf, re.compile(r"\bCPF/CNPJ\s*:\s*\d{10,11}\b", re.I)),
        (EntityType.cnpj, re.compile(r"\bCPF/CNPJ\s*:\s*\d{14}\b", re.I)),
        (EntityType.person, re.compile(r"\bTitular\s*:\s*([A-ZÀ-ÖØ-Ý][A-ZÀ-ÖØ-Ý '\.-]{5,120}?)(?=\s*\()", re.I)),
    ],
    DocumentKind.relatorio_investigativo: [
        (EntityType.functional_id, re.compile(r"\b(?:MATRICULA|MAT\.|MF|ID\s+FUNCIONAL)\s*(?:N[O.]*)?\s*[:\-]?\s*\d{3,12}(?:-\d)?\b", re.I)),
        (EntityType.pix, re.compile(r"\b(?:CHAVE\s+PIX|PIX)\s*(?:CPF|CNPJ|E-?MAIL|TELEFONE|ALEATORIA|EVP)?\s*[:\-]\s*[\w.@+\-/]{5,}\b", re.I)),
        (EntityType.email, re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)),
        (EntityType.vehicle_plate, re.compile(r"\b[A-Z]{3}[-\s]?\d[A-Z0-9]\d{2}\b", re.I)),
        (EntityType.address, re.compile(r"\b(?:Rua|Avenida|Av\.|Travessa|Estrada|Rodovia|Alameda)\s+[^,\n;]{3,80}(?:,\s*(?:n[ºo.]?\s*)?\d+[A-Za-z0-9\-]*)?(?:,\s*[^,\n;]{2,80})?(?:,\s*CEP\s*\d{5}-?\d{3})?", re.I)),
        (EntityType.bank_account, re.compile(r"\b(?:Ag(?:encia|\.)?\s*\d{1,6}(?:-\d)?\s*/?\s*)?(?:CC|C/C|Conta(?:\s+Corrente)?|Conta)\s*[:\-]?\s*\d{3,14}(?:-\d)?\b", re.I)),
        (EntityType.other_identifier, re.compile(r"(?<!\w)@[A-Z0-9._-]{3,40}\b", re.I)),
    ],
}


PROFILE_PROTECTED_PATTERNS: dict[DocumentKind, list[re.Pattern[str]]] = {
    DocumentKind.rif: [
        re.compile(r"\b(?:PIX|TED|DOC|SAQUE|DEPOSITO|TRANSFERENCIA|CREDITO|DEBITO|FRACIONAMENTO)\b", re.I),
        re.compile(r"\b(?:Indexador|idComunicacao|idOcorrencia|NumeroOcorrenciaBC|CodigoSegmento|CampoA|CampoB|CampoC|CampoD|CampoE)\b", re.I),
        re.compile(r"\b(?:cpfCnpjComunicante|nomeComunicante|CidadeAgencia|UFAgencia|NomeAgencia|NumeroAgencia)\b", re.I),
    ],
    DocumentKind.extrato_bancario: [
        re.compile(r"\b(?:ANEXO\s+[BC]|EXTRATO|DETALHADO|CONSOLIDADO|AGENCIA|CONTA|TIPO\s+CONTA|INSTITUICAO)\b", re.I),
        re.compile(r"\b(?:DEBITOS?|CREDITOS?|ABERTURA|ENCERRAMENTO|INICIO\s+MOV|FIM\s+MOV|IDENTIFICADOS?)\b", re.I),
        re.compile(r"\b(?:VALOR\s*\(R\$\)|HISTORICO|OBSERVACOES|QTD\.?\s+MOV|TOTAL|PAGINA|D/C)\b", re.I),
        re.compile(r"\b(?:BANCO|BCO|CAIXA\s+ECONOMICA|SICOOB|S\.A\.|CONTA\s+CORRENTE|CONTA\s+POUPANCA)\b", re.I),
        re.compile(r"\b(?:DOCUMENTO EXIGE RECUPERACAO MANUAL|PESQUISA CONCLUIDA|PORTADORES DE NUMERARIOS INFERIORES A DEZ MIL REAIS NAO SAO IDENTIFICADOS)\b", re.I),
        re.compile(r"\b(?:31/12/9999|9999-12-31|DOC\.\s*0)\b", re.I),
    ],
    DocumentKind.relatorio_investigativo: [
        re.compile(r"\b(?:IP|BO|B\.O\.|SEI|PROC\.?|PROCESSO|PORTARIA|OFICIO|RELATORIO|RI)\s*(?:N[ºO.]*)?\s*[:\-]?\s*[\w./-]{2,}\b", re.I),
        re.compile(r"\b(?:ART\.?|ARTIGO|LEI|DECRETO|CPP|CP|CONSTITUICAO|JURISPRUDENCIA|TIPIFICACAO)\b", re.I),
        re.compile(r"\b(?:POLICIA|MINISTERIO PUBLICO|TRIBUNAL|DELEGACIA|GARRAF|DRACO|COAF|BACEN|RECEITA FEDERAL|PCPE|PF)\b", re.I),
        re.compile(r"\b(?:IMEI|IMSI|ERB|ESTACAO RADIO BASE|WHATSAPP|INSTAGRAM|MERCADO PAGO|BANCO DO BRASIL|CAIXA|NUBANK|BRADESCO|SANTANDER)\b", re.I),
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
    DocumentKind.relatorio_investigativo: [
        re.compile(r"\bR\$\s?\d{1,3}(?:\.\d{3})*,\d{2}\b"),
        re.compile(r"\b\d{1,2}/\d{1,2}/\d{2,4}\b"),
        re.compile(r"\b(?:IP|BO|B\.O\.|SEI|PROC\.?|PROCESSO|PORTARIA|OFICIO|RELATORIO|RI)\s*(?:N[ºO.]*)?\s*[:\-]?\s*[\w./-]{2,}\b", re.I),
        re.compile(r"\b(?:ART\.?|ARTIGO|LEI|CPP|CP|FLS?\.?|ITEM|ANEXO)\b", re.I),
    ],
}


def profile_prompt(document_kind: DocumentKind) -> str:
    return PROFILE_PROMPTS[document_kind].strip()


def profile_regex_patterns(document_kind: DocumentKind) -> list[tuple[EntityType, re.Pattern[str]]]:
    return PROFILE_REGEX_PATTERNS.get(document_kind, [])


def profile_protected_patterns(document_kind: DocumentKind) -> list[re.Pattern[str]]:
    return PROFILE_PROTECTED_PATTERNS.get(document_kind, [])


def profile_output_terms(document_kind: DocumentKind) -> list[re.Pattern[str]]:
    return PROFILE_OUTPUT_TERMS.get(document_kind, [])
