import tempfile
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from app.models.schemas import AnonymizeOptions, DocumentKind

if "pydantic_settings" not in sys.modules:
    shim = types.ModuleType("pydantic_settings")
    shim.BaseSettings = object
    sys.modules["pydantic_settings"] = shim

from app.pipeline.runner import run_pipeline


class PersonalizedProfileTest(unittest.TestCase):
    def test_personalized_profile_prepares_manual_state_without_substitutions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "documento.txt"
            path.write_text("Maria da Silva CPF 123.456.789-09", encoding="utf-8")

            with patch("app.pipeline.runner.save_job"):
                result = run_pipeline(
                    path,
                    "documento.txt",
                    AnonymizeOptions(
                        document_kind=DocumentKind.personalizado,
                        model="qwen3:32b",
                        use_ollama=True,
                        request_title="Teste personalizado",
                    ),
                )

        self.assertEqual(result.document_kind, DocumentKind.personalizado)
        self.assertEqual(result.stats.replacements_applied, 0)
        self.assertEqual(result.audit.validation_status, "Aguardando finalizacao auditiva manual")
        self.assertIn("auditoria", result.audit.export_sha256)
        self.assertNotIn("pdf", result.audit.export_sha256)
        self.assertEqual(result.original_text, result.anonymized_text)


if __name__ == "__main__":
    unittest.main()
