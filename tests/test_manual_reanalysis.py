import unittest
import sys
import types

from app.models.schemas import EntityType, ManualCorrection

database_stub = types.ModuleType("app.services.database")
database_stub.save_job = lambda **_: None
sys.modules.setdefault("app.services.database", database_stub)

from app.pipeline.manual_reanalysis import _apply_rows, _finalize_manual_reports, _merge_manual_corrections


class ManualReanalysisTest(unittest.TestCase):
    def test_reports_applied_and_not_found_terms(self) -> None:
        original_text = "AYLA DE ARAUJO BESERRA realizou movimentacao. Nenhum outro nome consta."
        corrections = [
            ManualCorrection(original_value="AYLA DE ARAUJO BESERRA", entity_type=EntityType.person),
            ManualCorrection(original_value="NOME INEXISTENTE", entity_type=EntityType.person),
        ]

        rows, reports = _merge_manual_corrections([], corrections, original_text)
        anonymized_text, applied_total, updated_rows, counts = _apply_rows(original_text, rows)
        reports = _finalize_manual_reports(reports, counts)

        self.assertEqual(applied_total, 1)
        self.assertIn("[PESSOA_001]", anonymized_text)
        self.assertEqual(len(updated_rows), 1)
        self.assertEqual(reports[0].status, "aplicado")
        self.assertEqual(reports[0].occurrences, 1)
        self.assertEqual(reports[1].status, "nao_encontrado")
        self.assertEqual(reports[1].occurrences, 0)


if __name__ == "__main__":
    unittest.main()
