import unittest

from app.models.schemas import DocumentKind, Entity, EntityType
from app.pipeline.validator import validate_entities


class ValidatorRegressionTest(unittest.TestCase):
    def test_rif_public_entities_are_preserved(self) -> None:
        text = "nomeEnvolvido\nPOLICIA CIVIL DE PERNAMBUCO\nJOAO DA SILVA\n"
        public_start = text.index("POLICIA")
        person_start = text.index("JOAO")
        entities = [
            Entity(
                type=EntityType.organization,
                text="POLICIA CIVIL DE PERNAMBUCO",
                start=public_start,
                end=public_start + len("POLICIA CIVIL DE PERNAMBUCO"),
                source="test",
            ),
            Entity(
                type=EntityType.person,
                text="JOAO DA SILVA",
                start=person_start,
                end=person_start + len("JOAO DA SILVA"),
                source="test",
            ),
        ]

        valid, _, _, warnings = validate_entities(text, entities, DocumentKind.rif)

        self.assertEqual([entity.text for entity in valid], ["JOAO DA SILVA"])
        self.assertTrue(any("entidade publica" in warning for warning in warnings))

    def test_delos_preservation_warnings_are_consolidated(self) -> None:
        text = "Extraido do Sistema Delos\nHistorico\nJUROS\nJUROS\nJUROS\n"
        starts = [index for index in (text.find("JUROS"), text.find("JUROS", text.find("JUROS") + 1), text.rfind("JUROS"))]
        entities = [
            Entity(type=EntityType.person, text="JUROS", start=start, end=start + len("JUROS"), source="test")
            for start in starts
        ]

        valid, _, _, warnings = validate_entities(text, entities, DocumentKind.extrato_bancario)

        self.assertEqual(valid, [])
        self.assertEqual(len(warnings), 1)
        self.assertIn("Ocorrencias consolidadas: 3", warnings[0])

    def test_bank_statement_preserves_doc_column_values(self) -> None:
        text = "Data Doc. Historico Valor\n01/01/2024 123456 PAGTO CARTAO CREDITO 100,00\n"
        start = text.index("123456")
        entities = [
            Entity(type=EntityType.cep, text="123456", start=start, end=start + len("123456"), source="test")
        ]

        valid, _, _, warnings = validate_entities(text, entities, DocumentKind.extrato_bancario)

        self.assertEqual(valid, [])
        self.assertTrue(any("numero operacional de extrato bancario" in warning for warning in warnings))

    def test_bank_statement_preserves_operational_numbers_but_keeps_valid_cpf(self) -> None:
        text = (
            "Titular: ALINE MARIA DE SOUZA CPF/CNPJ: 11144477735\n"
            "Data Doc. Historico Valor\n"
            "01/01/2024 876543 PAGAMENTO CONTA AGUA 100,00\n"
        )
        doc_start = text.index("876543")
        cpf_start = text.index("11144477735")
        entities = [
            Entity(type=EntityType.other_identifier, text="876543", start=doc_start, end=doc_start + 6, source="test"),
            Entity(type=EntityType.cpf, text="11144477735", start=cpf_start, end=cpf_start + 11, source="test"),
        ]

        valid, _, _, _ = validate_entities(text, entities, DocumentKind.extrato_bancario)

        self.assertEqual([entity.text for entity in valid], ["11144477735"])


if __name__ == "__main__":
    unittest.main()
