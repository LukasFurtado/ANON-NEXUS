import re
import unicodedata

from app.models.schemas import EntityType


ALLOWLIST_HISTORICO = {
    "JUROS",
    "COBRANCA DE JUROS",
    "ALTERACAO DE RAZAO",
    "TRANSFERIDO DA POUPANCA",
    "TRANSFERIDO PARA POUPANCA",
    "DEVOLUCAO CHEQUE DEPOSITADO",
    "COMPRA COM CARTAO",
    "SAQUE COM CARTAO",
    "SAQUE ATM",
    "SAQUE",
    "DEPOSITO ONLINE",
    "DEPOSITO EM DINHEIRO",
    "DEPOSITO BLOQUEADO 1 DIA UTIL",
    "DESBLOQUEIO DE DEPOSITO",
    "DEPOSITO COMPE",
    "DEPOS.COMPE",
    "DEP.DINHEIRO",
    "DP DINH AG",
    "DEPOSITO EM CHEQUE",
    "DEPOSITO BLOQ. 1 DIA UTIL",
    "PAGAMENTO DE TITULO",
    "PAGAMENTO CONTA AGUA",
    "PAGAMENTO CONTA LUZ",
    "PAGAMENTO CONTA TELEFONE",
    "PAGAMENTO CONTA",
    "PAGTO CARTAO CREDITO",
    "MOVIMENTO DO DIA",
    "MOVIMENTACAO DO DIA",
    "AVISO CREDIT",
    "CRED.AUTOR",
    "CREDITO AUTORIZADO",
    "TRANSF.CRED.",
    "TRANSF CTA",
    "TRANSFERENCIA",
    "TRANSFERENCIA ON LINE",
    "TRANSFERIDO PARA POUPANCA",
    "TRANSFERIDO DA POUPANCA",
    "TED",
    "TED TRANSFERENCIA ELETR.DISPON",
    "DEBITO TED",
    "TEDPESSOAL",
    "DOC",
    "BLOQ. 1 DIA",
    "BLOQUEIO 1 DIA UTIL",
    "APLICACAO",
    "APLICACAO EM POUPANCA",
    "INVESTIMENTO APLICACAO",
    "RESG AUTOM",
    "RESGATE DE APLICACAO",
    "RESGATE AUTOM",
    "RESGATE",
    "RETIRADA",
    "DEB CESTA",
    "SAQ CARTAO",
    "TAR SAQUE-C",
    "TAR SAQUE-T",
    "TAR SAQUE-P",
    "TARIFA DE PACOTE DE SERVICOS",
    "TARIFA DE DOC OU TED",
    "TARIFAS SERVICOS DIVERSOS",
    "TARIFA SAQUE CAIXA ATE R 1MIL",
    "TARIFA MSG",
    "ESTORNO ACERTO-CREDITO",
    "ESTORNO DE DEBITO",
    "ESTORNO SISTEMA AGE",
    "BB-PRESTACAO SERVICOS",
    "POUPANCA OURO-DEP A PRAZO",
    "RECEITA DE TARIFAS",
    "CONTRAPARTIDA DO LANC.EM CONTA INTERNA",
    "PESQUISA CONCLUIDA",
    "PAGAMENTO EFETUADO COM PONTOS",
    "PORTADORES DE NUMERARIOS INFERIORES A DEZ MIL REAIS NAO SAO IDENTIFICADOS",
    "RELATIVO A TRANSACAO COM CARTAO DE DEBITO",
    "SAQUE EM TERMINAL DE AUTOATENDIMENTO",
    "DOCUMENTO EXIGE RECUPERACAO MANUAL",
}

PREFIXOS_OPERACIONAIS = ("BB1-", "BB2-", "CEF-", "CRED ", "DEB ", "TAR ", "SAQ ", "DEP ", "DP ", "TED")
VALORES_NULOS_DELOS = {"000000000000", "00000000000000", "0", "000", "0000", ""}
CODIGOS_ISPB_COMPE = {
    "1",
    "33",
    "36",
    "41",
    "47",
    "70",
    "77",
    "84",
    "94",
    "104",
    "107",
    "136",
    "184",
    "189",
    "191",
    "212",
    "237",
    "260",
    "290",
    "318",
    "323",
    "336",
    "341",
    "389",
    "422",
    "505",
    "633",
    "637",
    "745",
    "748",
    "756",
}

DELOS_COLUMNS = (
    "DATA",
    "HISTORICO",
    "DOC.",
    "VALOR",
    "D/C",
    "CPF/CNPJ",
    "NOME BENEF/DEPOS",
    "INST.",
    "AG",
    "CONTA",
    "OBSERVACOES",
)

PROTECTED_OPERATIONAL_TYPES = {
    EntityType.person,
    EntityType.organization,
    EntityType.phone,
    EntityType.cep,
    EntityType.card,
    EntityType.other_identifier,
}


def normalizar(texto: str) -> str:
    nfkd = unicodedata.normalize("NFKD", texto or "")
    sem_acento = "".join(char for char in nfkd if not unicodedata.combining(char))
    return re.sub(r"\s+", " ", sem_acento.upper()).strip()


def documento_e_delos(texto: str) -> bool:
    normalizado = normalizar(texto)
    if "EXTRAIDO DO SISTEMA DELOS" in normalizado or "DELOS - SISTEMA DE CONTROLE" in normalizado:
        return True
    return sum(1 for coluna in DELOS_COLUMNS if coluna in normalizado) >= 6


def historico_deve_preservar(valor: str) -> bool:
    normalizado = normalizar(valor)
    if normalizado in {normalizar(item) for item in ALLOWLIST_HISTORICO}:
        return True
    return any(normalizado.startswith(normalizar(prefixo)) for prefixo in PREFIXOS_OPERACIONAIS)


def valor_e_nulo_delos(valor: str) -> bool:
    return normalizar(valor) in VALORES_NULOS_DELOS


def cnpj_cabecalho_preservar(valor: str) -> bool:
    digits = re.sub(r"\D", "", valor or "").lstrip("0") or "0"
    return bool(re.fullmatch(r"\d{1,3}", digits) and digits in CODIGOS_ISPB_COMPE)


def should_preserve_entity(fragment: str, line_context: str, entity_type: EntityType) -> tuple[bool, str]:
    value = normalizar(fragment)
    line = normalizar(line_context)
    digits = re.sub(r"\D", "", fragment or "")

    if not value:
        return True, "marcacao vazia descartada no perfil extrato_bancario"
    if historico_deve_preservar(value) and entity_type in PROTECTED_OPERATIONAL_TYPES:
        return True, "termo operacional de historico bancario preservado"
    if valor_e_nulo_delos(value):
        return True, "placeholder nulo operacional do DELOS preservado"
    if cnpj_cabecalho_preservar(value):
        return True, "codigo ISPB/COMPE preservado"
    if re.search(r"\b(?:REQUISICAO|NUMERO DE CASO)\b", line):
        return True, "identificador do caso preservado"
    if "DOC." in line and digits and entity_type in {EntityType.other_identifier, EntityType.phone, EntityType.card}:
        return True, "valor operacional da coluna Doc. preservado"
    if entity_type in {EntityType.cep, EntityType.phone, EntityType.card, EntityType.other_identifier} and _numero_operacional_bancario(digits, line):
        return True, "numero operacional de extrato bancario preservado"
    if re.search(r"\bINST\.?\b", line) and cnpj_cabecalho_preservar(value):
        return True, "codigo de instituicao financeira preservado"
    if entity_type == EntityType.phone and re.fullmatch(r"\d{4,12}", digits):
        if re.search(r"\b(?:AG|CONTA|INST\.?)\b", line):
            return True, "agencia, conta ou codigo bancario preservado"
    return False, ""


def _numero_operacional_bancario(digits: str, line: str) -> bool:
    if not digits:
        return False
    if len(digits) <= 4 and re.search(r"\b(?:DOC|DOC\.|INST|AG|CONTA|HISTORICO|VALOR)\b", line):
        return True
    if len(digits) in {5, 6, 7, 8} and not re.search(r"\b(?:CEP|ENDERECO|RUA|AVENIDA|TELEFONE|FONE|CELULAR)\b", line):
        return True
    if len(digits) >= 9 and re.search(
        r"\b(?:PAGTO|PAGAMENTO|CARTAO|CREDITO|DEBITO|SAQUE|TARIFA|TED|DOC|TRANSFERENCIA|HISTORICO|VALOR|D/C|INST|AG|CONTA)\b",
        line,
    ):
        return True
    return False
