import unittest

from app.core.confidence import compute_confidence
from app.core.human_review import build_review_items
from app.models.schemas import AnonymizationControlRow
from app.pipeline.exporter import _pdf_marker_font_size, _pdf_search_candidates


class ConfidenceReviewPdfTest(unittest.TestCase):
    def test_pdf_search_candidates_include_bank_statement_identifier_variants(self) -> None:
        candidates = _pdf_search_candidates("11144477735")

        self.assertIn("11144477735", candidates)
        self.assertIn("111.444.777-35", candidates)
        self.assertIn("111 444 777 35", candidates)

    def test_pdf_marker_font_size_shrinks_for_narrow_rect(self) -> None:
        class Rect:
            width = 22
            height = 9

        size = _pdf_marker_font_size(Rect(), "[CPF_001]")

        self.assertGreaterEqual(size, 4.2)
        self.assertLess(size, 8)

    def test_confidence_penalizes_fallback_and_residuals(self) -> None:
        result = compute_confidence(
            replacements_applied=2,
            validation_warnings=["aviso"],
            post_validation={"residual_entities": 2, "structure_warnings": 1},
            ollama_metrics={"json_rejected_chunks": 1, "failure_reason": "timeout"},
            structure_preserved=True,
            ocr_used=False,
        )

        self.assertLess(result.score, 65)
        self.assertEqual(result.level, "BAIXA")
        self.assertTrue(any("fallback" in reason.lower() for reason in result.reasons))

    def test_review_items_include_entities_warnings_and_confidence(self) -> None:
        rows = [
            AnonymizationControlRow(
                original_value="JOAO SILVA",
                entity_type="Pessoa",
                anonymous_id="[PESSOA_001]",
                occurrences=3,
            )
        ]

        items = build_review_items(
            control_rows=rows,
            validation_warnings=["Possiveis identificadores remanescentes apos anonimizacao: CPF=1."],
            post_validation={"residual_entities": 1, "residual_by_type": {"CPF": 1}},
            confidence={"score": 60, "level": "BAIXA"},
        )

        categories = {item["category"] for item in items}
        self.assertIn("entidade", categories)
        self.assertIn("aviso", categories)
        self.assertIn("pos_validacao", categories)
        self.assertIn("confiabilidade", categories)


if __name__ == "__main__":
    unittest.main()
