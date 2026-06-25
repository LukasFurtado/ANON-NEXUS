import unittest

from app.models.schemas import DocumentKind
from app.pipeline.post_validator import validate_post_anonymization


class PostAnonymizationValidatorTest(unittest.TestCase):
    def test_detects_residual_sensitive_identifier_without_exposing_value(self) -> None:
        original = "JOAO SILVA CPF 111.444.777-35"
        anonymized = "[PESSOA_001] CPF 111.444.777-35"

        result = validate_post_anonymization(original, anonymized, DocumentKind.rif, "relatorio.txt")

        self.assertGreater(result.residual_entities, 0)
        self.assertLess(result.score, 100)
        self.assertTrue(any("CPF=" in warning for warning in result.warnings))
        self.assertFalse(any("111.444.777-35" in warning for warning in result.warnings))

    def test_warns_about_possible_truncated_cpf_without_exposing_value(self) -> None:
        original = "JOAO SILVA CPF 001.234.567-97"
        anonymized = "[PESSOA_001] CPF [CPF_001]\nOutro CPF 0123456797"

        result = validate_post_anonymization(original, anonymized, DocumentKind.rif, "relatorio.txt")

        self.assertLess(result.score, 100)
        self.assertTrue(any("zero inicial removido" in warning for warning in result.warnings))
        self.assertFalse(any("0123456797" in warning for warning in result.warnings))

    def test_detects_csv_structure_break(self) -> None:
        original = "Indexador;cpfCnpjEnvolvido;nomeEnvolvido\n1;11144477735;JOAO SILVA\n"
        anonymized = "Indexador;cpfCnpjEnvolvido;nomeEnvolvido\n1;[CPF_001]\n"

        result = validate_post_anonymization(original, anonymized, DocumentKind.rif, "RIF138538_Envolvidos.csv")

        self.assertGreater(result.structure_warnings, 0)
        self.assertTrue(any("CSV" in warning for warning in result.warnings))


if __name__ == "__main__":
    unittest.main()
