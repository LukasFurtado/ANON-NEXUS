import unittest
from pathlib import Path
import tempfile

from app.models.schemas import DocumentKind, Entity, EntityType
from app.pipeline.ocr import needs_ocr
from app.pipeline.parser import extract_text, inspect_source_document
from app.pipeline.post_validator import validate_post_anonymization
from app.pipeline.validator import validate_entities


class PipelineStageImprovementsTest(unittest.TestCase):
    def test_parser_metadata_identifies_csv_shape(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "RIF123_Envolvidos.csv"
            path.write_text("Indexador;cpfCnpjEnvolvido;nomeEnvolvido\n1;11144477735;JOAO SILVA\n", encoding="utf-8")

            text = extract_text(path)
            metadata = inspect_source_document(path, text)

        self.assertEqual(metadata["extension"], ".csv")
        self.assertEqual(metadata["likely_delimiter"], ";")
        self.assertTrue(metadata["has_tabular_text"])
        self.assertGreater(metadata["text_lines"], 1)

    def test_ocr_heuristic_uses_alphanumeric_density(self) -> None:
        self.assertTrue(needs_ocr("   \n---   ..."))
        self.assertFalse(needs_ocr("Texto extraido com conteudo suficiente " * 8))

    def test_validator_warnings_do_not_include_sensitive_fragment(self) -> None:
        text = "Lei 12345678901 deve ser preservada como referencia juridica."
        start = text.index("Lei")
        entities = [Entity(type=EntityType.person, text="Lei 12345678901", start=start, end=start + 15, source="test")]

        _, _, _, warnings = validate_entities(text, entities, DocumentKind.relatorio_investigativo)

        self.assertTrue(warnings)
        self.assertFalse(any("12345678901" in warning for warning in warnings))

    def test_post_validator_flags_marker_absence_and_large_loss(self) -> None:
        original = "JOAO SILVA CPF 111.444.777-35\n" * 10
        anonymized = "JOAO SILVA CPF 111.444.777-35"

        result = validate_post_anonymization(original, anonymized, DocumentKind.rif, "relatorio.txt")

        self.assertLess(result.score, 100)
        self.assertEqual(result.anonymous_markers, 0)
        self.assertTrue(any("Nenhum marcador anonimo" in warning for warning in result.warnings))
        self.assertTrue(any("muito menor" in warning or "linhas" in warning for warning in result.warnings))


if __name__ == "__main__":
    unittest.main()
