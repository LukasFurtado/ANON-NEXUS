import unittest

from app.core.safe_summary import generate_safe_summary


class SafeSummaryTest(unittest.TestCase):
    def test_summary_removes_sensitive_warning_fragments(self) -> None:
        summary = generate_safe_summary(
            {
                "original_text": "JOAO SILVA CPF 123.456.789-00",
                "document_kind": "rif",
                "entities": [{"type": "CPF"}],
                "stats": {
                    "entities_found": 1,
                    "replacements_applied": 1,
                    "validation_warnings": ["123.456.789-00", "termo generico descartado"],
                },
                "audit": {
                    "source_sha256": "ABC",
                    "export_sha256": {"pdf": "DEF"},
                    "processing_time_seconds": 1.2,
                },
                "pipeline_stages_ok": ["parser", "ner", "regex", "substitution", "validation", "export"],
            }
        )

        self.assertEqual(summary["document_id"], "ABC")
        self.assertNotIn("123.456.789-00", summary["warnings_raised"])
        self.assertIn("termo generico descartado", summary["warnings_raised"])


if __name__ == "__main__":
    unittest.main()
