import unittest
import sys
import tempfile
import types
from pathlib import Path

from app.models.schemas import AnonymizationControlRow, EntityType, ManualCorrection

database_stub = types.ModuleType("app.services.database")
database_stub.save_job = lambda **_: None
sys.modules.setdefault("app.services.database", database_stub)

from app.pipeline.manual_reanalysis import _apply_rows, _finalize_manual_reports, _merge_manual_corrections
from app.pipeline.exporter import _export_control_pdf


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

    def test_existing_row_marker_can_be_updated(self) -> None:
        original_text = "AYLA DE ARAUJO BESERRA realizou movimentacao."
        rows = [
            AnonymizationControlRow(
                original_value="AYLA DE ARAUJO BESERRA",
                entity_type="Pessoa",
                anonymous_id="[PESSOA_001]",
                occurrences=1,
            )
        ]
        corrections = [
            ManualCorrection(
                original_value="AYLA DE ARAUJO BESERRA",
                entity_type=EntityType.person,
                anonymous_id="[PESSOA_999]",
            )
        ]

        updated_rows, reports = _merge_manual_corrections(rows, corrections, original_text)
        anonymized_text, applied_total, _, counts = _apply_rows(original_text, updated_rows)
        reports = _finalize_manual_reports(reports, counts)

        self.assertEqual(applied_total, 1)
        self.assertIn("[PESSOA_999]", anonymized_text)
        self.assertNotIn("[PESSOA_001]", anonymized_text)
        self.assertEqual(updated_rows[0].anonymous_id, "[PESSOA_999]")
        self.assertEqual(reports[0].status, "aplicado")

    def test_control_pdf_includes_manual_reanalysis_updates(self) -> None:
        metadata = {
            "request_title": "Teste",
            "document_kind": "rif",
            "model": "qwen3:32b",
            "anon_version": "2.0.0",
            "source_sha256": "ABC123",
            "control_table": [
                {
                    "original_value": "AYLA DE ARAUJO BESERRA",
                    "entity_type": "Pessoa",
                    "anonymous_id": "[PESSOA_999]",
                    "occurrences": 1,
                }
            ],
            "manual_reanalysis": {
                "report": [
                    {
                        "requested_value": "AYLA DE ARAUJO BESERRA",
                        "entity_type": "Pessoa",
                        "anonymous_id": "[PESSOA_999]",
                        "occurrences": 1,
                        "status": "aplicado",
                        "note": "Marcador existente atualizado por decisao registrada no painel de auditoria.",
                    }
                ]
            },
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "controle.pdf"
            _export_control_pdf(path, "origem.txt", metadata)
            self.assertTrue(path.exists())
            self.assertGreater(path.stat().st_size, 0)
            try:
                from pypdf import PdfReader
            except Exception:
                return
            text = "\n".join(page.extract_text() or "" for page in PdfReader(str(path)).pages)
            self.assertIn("ATUALIZACOES POR REANALISE DIRIGIDA", text)
            self.assertIn("[PESSOA_999]", text)


if __name__ == "__main__":
    unittest.main()
