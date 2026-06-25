import json
import sys
import types
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

if "pydantic_settings" not in sys.modules:
    shim = types.ModuleType("pydantic_settings")
    shim.BaseSettings = object
    sys.modules["pydantic_settings"] = shim

from app.pipeline.exporter import export_audit_manifest


class AuditManifestTest(unittest.TestCase):
    def test_audit_manifest_separates_external_and_internal_products(self) -> None:
        with TemporaryDirectory() as tmpdir:
            cwd = Path.cwd()
            try:
                import os

                os.chdir(tmpdir)
                path = export_audit_manifest(
                    "job-1",
                    "documento.pdf",
                    {
                        "request_title": "IP 123",
                        "document_kind": "rif",
                        "model": "qwen3:32b",
                        "anon_version": "test",
                        "source_sha256": "AAA",
                        "validation_warnings": ["aviso"],
                        "control_table": [{"original_value": "A", "anonymous_id": "[PESSOA_001]"}],
                    },
                    {"pdf": "PDFHASH", "controle": "CONTROLHASH", "avisos": "WARNINGHASH"},
                )
                payload = json.loads(Path(path).read_text(encoding="utf-8"))
            finally:
                os.chdir(cwd)
        products = {item["format"]: item for item in payload["products"]}

        self.assertEqual(payload["schema"], "ANON-AUDITORIA-INTERNA-v1")
        self.assertTrue(products["pdf"]["external_sharing_allowed"])
        self.assertFalse(products["controle"]["external_sharing_allowed"])
        self.assertTrue(products["controle"]["contains_original_values"])
        self.assertIn("internal_restricted_products", payload["product_policy"])


if __name__ == "__main__":
    unittest.main()
