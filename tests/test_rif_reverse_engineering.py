import unittest

from app.core.profile_loader import profile_context_prompt
from app.models.schemas import DocumentKind, EntityType
from app.pipeline.regex_rules import detect_entities_by_regex
from app.pipeline.rif_rules import RIF_COMUNICACOES, RIF_ENVOLVIDOS, RIF_OCORRENCIAS, detect_rif_csv_subtype
from app.pipeline.validator import validate_entities
from app.services.knowledge_base import compact_profile_guidance


ENVOLVIDOS = (
    "Indexador;cpfCnpjEnvolvido;nomeEnvolvido;tipoEnvolvido;agenciaEnvolvido;contaEnvolvido;"
    "DataAberturaConta;DataAtualizacaoConta;bitPepCitado;bitPessoaObrigadaCitado;intServidorCitado\n"
    "1;12345678901;JOAO CARLOS DA SILVA;Titular;1234;98765-0;01/01/2024;02/01/2024;Nao;Nao;-\n"
)

OCORRENCIAS = "Indexador;idOcorrencia;Ocorrencia\n1;204;Depositos em especie fracionados em valores abaixo do limite operacional\n"

COMUNICACOES = (
    "Indexador;idComunicacao;NumeroOcorrenciaBC;Data_do_Recebimento;Data_da_operacao;DataFimFato;"
    "cpfCnpjComunicante;nomeComunicante;CidadeAgencia;UFAgencia;NomeAgencia;NumeroAgencia;"
    "informacoesAdicionais;CampoA;CampoB;CampoC;CampoD;CampoE;CodigoSegmento\n"
    "1;777;888;01/02/2024;02/02/2024;03/02/2024;191;BANCO DO BRASIL SA;RECIFE;PE;"
    "AGENCIA CENTRO;1234;Remessa realizada por JOAO CARLOS DA SILVA CPF 12345678909 para MARIA OLIVEIRA CPF 98765432100;"
    "1000,00;2000,00;3000,00;;;1\n"
)


class RifReverseEngineeringTest(unittest.TestCase):
    def test_detects_rif_subtypes_by_filename_and_header(self) -> None:
        self.assertEqual(detect_rif_csv_subtype("", "RIF138538_Envolvidos.csv"), RIF_ENVOLVIDOS)
        self.assertEqual(detect_rif_csv_subtype(OCORRENCIAS, None), RIF_OCORRENCIAS)
        self.assertEqual(detect_rif_csv_subtype(COMUNICACOES, None), RIF_COMUNICACOES)

    def test_envolvidos_anonymizes_only_sensitive_columns(self) -> None:
        entities = detect_entities_by_regex(ENVOLVIDOS, DocumentKind.rif, "RIF138538_Envolvidos.csv")
        texts = {entity.text for entity in entities}

        self.assertIn("12345678901", texts)
        self.assertIn("JOAO CARLOS DA SILVA", texts)
        self.assertIn("1234", texts)
        self.assertIn("98765-0", texts)
        self.assertNotIn("Titular", texts)
        self.assertNotIn("Nao", texts)

    def test_ocorrencias_preserves_operational_table(self) -> None:
        entities = detect_entities_by_regex(OCORRENCIAS, DocumentKind.rif, "RIF138538_Ocorrencias.csv")
        texts = {entity.text for entity in entities}

        self.assertNotIn("204", texts)
        self.assertFalse(any("Depositos em especie" in text for text in texts))

    def test_comunicacoes_preserves_bank_and_detects_narrative_entities(self) -> None:
        candidates = detect_entities_by_regex(COMUNICACOES, DocumentKind.rif, "RIF138538_Comunicacoes.csv")
        valid, *_ = validate_entities(COMUNICACOES, candidates, DocumentKind.rif)
        texts = {entity.text for entity in valid}

        self.assertNotIn("BANCO DO BRASIL SA", texts)
        self.assertIn("JOAO CARLOS DA SILVA", texts)
        self.assertTrue(any(entity.type in {EntityType.cpf, EntityType.other_identifier} and entity.text == "12345678909" for entity in valid))

    def test_rif_reverse_engineering_reaches_prompts(self) -> None:
        prompt = profile_context_prompt(DocumentKind.rif.value)
        guidance = compact_profile_guidance(DocumentKind.rif)

        self.assertIn("Engenharia reversa RIF ativa", prompt)
        self.assertIn("rif_envolvidos", prompt)
        self.assertIn("ENGENHARIA REVERSA RIF", guidance)
        self.assertIn("RIF[numeros]_Comunicacoes.csv", guidance)


if __name__ == "__main__":
    unittest.main()
