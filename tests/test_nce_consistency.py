import unittest

from app.core.nce import NCEGroupContext, canonical_entity_key, expected_sensitive_domains
from app.models.schemas import DocumentKind, Entity, EntityType
from app.pipeline.anonymizer import ReplacementState, apply_anonymization


class NCEConsistencyTest(unittest.TestCase):
    def test_canonical_key_unifies_accents_case_and_document_format(self) -> None:
        self.assertEqual(
            canonical_entity_key("PERSON", "Joao Carlos da Silva"),
            canonical_entity_key("PERSON", "JOAO CARLOS DA SILVA"),
        )
        self.assertEqual(
            canonical_entity_key("CPF", "123.456.789-09"),
            canonical_entity_key("CPF", "012345678909"),
        )

    def test_replacement_state_is_consistent_across_files(self) -> None:
        state = ReplacementState()
        first = "JOAO CARLOS DA SILVA CPF 123.456.789-09"
        second = "Joao Carlos da Silva CPF 012345678909"
        first_name_start = first.index("JOAO")
        first_cpf_start = first.index("123")
        second_name_start = second.index("Joao")
        second_cpf_start = second.index("012")

        first_entities = [
            Entity(type=EntityType.person, text="JOAO CARLOS DA SILVA", start=first_name_start, end=first_name_start + len("JOAO CARLOS DA SILVA"), source="test"),
            Entity(type=EntityType.cpf, text="123.456.789-09", start=first_cpf_start, end=first_cpf_start + len("123.456.789-09"), source="test"),
        ]
        second_entities = [
            Entity(type=EntityType.person, text="Joao Carlos da Silva", start=second_name_start, end=second_name_start + len("Joao Carlos da Silva"), source="test"),
            Entity(type=EntityType.cpf, text="012345678909", start=second_cpf_start, end=second_cpf_start + len("012345678909"), source="test"),
        ]

        first_output, _, first_rows = apply_anonymization(first, first_entities, state)
        second_output, _, second_rows = apply_anonymization(second, second_entities, state)

        self.assertIn("[PESSOA_001]", first_output)
        self.assertIn("[PESSOA_001]", second_output)
        self.assertIn("[CPF_001]", first_output)
        self.assertIn("[CPF_001]", second_output)
        self.assertEqual(first_rows[0].anonymous_id, second_rows[0].anonymous_id)

    def test_nce_group_detects_rif_file_roles(self) -> None:
        context = NCEGroupContext.start(request_title="IP TESTE", document_kind=DocumentKind.rif, model="qwen3:32b")
        file_context = context.prepare_file(
            filename="RIF138538_Envolvidos.csv",
            text="Indexador;cpfCnpjEnvolvido;nomeEnvolvido;tipoEnvolvido;agenciaEnvolvido;contaEnvolvido\n1;123;JOAO;Titular;1;2\n",
        )

        self.assertEqual(file_context.subtype, "rif_envolvidos")
        self.assertEqual(file_context.role_label, "RIF Envolvidos")
        self.assertIn("nome", file_context.expected_sensitive_domains)
        self.assertEqual(context.public_metadata()["dictionary_size"], 0)

    def test_nce_records_processing_coordination(self) -> None:
        context = NCEGroupContext.start(request_title="IP TESTE", document_kind=DocumentKind.rif, model="qwen3:32b")
        file_context = context.prepare_file(
            filename="RIF138538_Comunicacoes.csv",
            text=(
                "Indexador;idComunicacao;NumeroOcorrenciaBC;Data_do_Recebimento;Data_da_operacao;"
                "cpfCnpjComunicante;nomeComunicante;informacoesAdicionais;CodigoSegmento\n"
            ),
            source_sha256="ABC123",
            extension=".csv",
        )
        context.coordinate(file_context, stage="regex", status="completed", summary="candidatos locais", candidates=3)

        metadata = context.public_metadata()
        file_metadata = metadata["files"][0]
        stages = [item["stage"] for item in file_metadata["coordination_log"]]

        self.assertEqual(file_metadata["source_sha256"], "ABC123")
        self.assertIn("contraparte", file_metadata["expected_sensitive_domains"])
        self.assertIn("context", stages)
        self.assertIn("regex", stages)

    def test_nce_expected_domains_are_profile_specific(self) -> None:
        self.assertIn("titular", expected_sensitive_domains(DocumentKind.extrato_bancario, "extrato_bancario"))
        self.assertIn("endereco", expected_sensitive_domains(DocumentKind.relatorio_investigativo, "relatorio_investigativo"))


if __name__ == "__main__":
    unittest.main()
