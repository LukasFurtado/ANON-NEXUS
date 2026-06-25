import unittest

from app.core.quality_classifier import classify_quality


class QualityClassifierTest(unittest.TestCase):
    def test_good_when_all_required_stages_exist(self) -> None:
        result = classify_quality(
            {
                "pipeline_stages_ok": ["parser", "ner", "regex", "substitution", "validation", "export"],
                "total_entities_detected": 10,
                "warnings_raised": [],
            },
            {"anonymize_always": ["CPF", "Pessoa"]},
        )
        self.assertEqual(result.status, "BOM")

    def test_critical_when_stage_is_missing(self) -> None:
        result = classify_quality(
            {
                "pipeline_stages_ok": ["parser", "regex", "substitution"],
                "total_entities_detected": 0,
                "warnings_raised": [],
            },
            {"anonymize_always": ["CPF", "Pessoa"]},
        )
        self.assertEqual(result.status, "ATENCAO_CRITICA")


if __name__ == "__main__":
    unittest.main()
