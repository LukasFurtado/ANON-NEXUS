import unittest

from app.models.schemas import Entity, EntityType
from app.pipeline.anonymizer import apply_anonymization


class AnonymizerRegressionTest(unittest.TestCase):
    def test_numeric_branch_does_not_replace_same_value_globally(self) -> None:
        text = "Indexador;agenciaEnvolvido\n1;1\n1;2\n"
        start = text.index(";1\n") + 1
        anonymized, applied, _ = apply_anonymization(
            text,
            [Entity(type=EntityType.bank_branch, text="1", start=start, end=start + 1, source="test")],
        )

        self.assertIn("Indexador;agenciaEnvolvido\n1;[AGENCIA_001]\n1;2", anonymized)
        self.assertEqual(applied, 1)

    def test_overlapping_entities_are_not_double_replaced(self) -> None:
        text = "CPF 123.456.789-00"
        start = text.index("123")
        entities = [
            Entity(type=EntityType.other_identifier, text="123.456.789-00", start=start, end=len(text), source="test"),
            Entity(type=EntityType.cpf, text="123.456.789-00", start=start, end=len(text), source="test"),
        ]

        anonymized, applied, rows = apply_anonymization(text, entities)

        self.assertEqual(anonymized, "CPF [CPF_001]")
        self.assertEqual(applied, 1)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].anonymous_id, "[CPF_001]")


if __name__ == "__main__":
    unittest.main()
