import sys
import types
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

if "pydantic_settings" not in sys.modules:
    shim = types.ModuleType("pydantic_settings")
    shim.BaseSettings = object
    sys.modules["pydantic_settings"] = shim

from app.core.hybrid_security import (
    ENRICHMENT_MODE,
    HybridSecurityError,
    HybridSecurityManager,
    contains_sensitive_pattern,
    allowed_public_sources,
    blocked_external_api_requests,
)
from app.core.config import settings


class HybridSecurityTest(unittest.TestCase):
    def test_default_mode_allows_only_offline_processing(self) -> None:
        manager = HybridSecurityManager(mode="OFFLINE", enrichment_enabled=False)

        manager.require_offline_processing()
        self.assertEqual(manager.status()["mode"], "OFFLINE")
        self.assertTrue(manager.status()["processing_allowed"])

    def test_processing_is_blocked_in_enrichment_mode(self) -> None:
        manager = HybridSecurityManager(mode=ENRICHMENT_MODE, enrichment_enabled=True)

        with self.assertRaises(HybridSecurityError):
            manager.require_offline_processing()
        self.assertEqual(manager.mode, "OFFLINE")

    def test_enrichment_is_disabled_by_default(self) -> None:
        manager = HybridSecurityManager(mode="OFFLINE", enrichment_enabled=False)

        with self.assertRaises(HybridSecurityError):
            manager.begin_enrichment()

    def test_public_source_whitelist_requires_https(self) -> None:
        manager = HybridSecurityManager(mode="OFFLINE", enrichment_enabled=False)

        self.assertTrue(manager.validate_public_source_url("https://servicodados.ibge.gov.br/api/v1/localidades/municipios"))
        self.assertFalse(manager.validate_public_source_url("http://servicodados.ibge.gov.br/api/v1/localidades/municipios"))
        self.assertFalse(manager.validate_public_source_url("https://example.com/upload"))
        self.assertTrue(manager.validate_public_source_url("https://brasilapi.com.br/api/banks/v1"))

    def test_content_gate_blocks_sensitive_patterns(self) -> None:
        self.assertTrue(contains_sensitive_pattern("Joao, CPF 123.456.789-09"))
        self.assertTrue(contains_sensitive_pattern("RIF sigiloso de investigado"))
        self.assertFalse(contains_sensitive_pattern("Lista publica de municipios brasileiros"))

    def test_automatic_download_writes_public_source_and_manifest(self) -> None:
        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self) -> bytes:
                return b'[{"id": 2611606, "nome": "Recife"}]'

        with TemporaryDirectory() as tmpdir:
            original_data_dir = settings.data_dir
            settings.data_dir = Path(tmpdir)
            try:
                manager = HybridSecurityManager(mode="OFFLINE", enrichment_enabled=True)
                with patch("urllib.request.urlopen", return_value=FakeResponse()):
                    result = manager.run_automatic_downloads(source_keys=["ibge_municipios"])
            finally:
                settings.data_dir = original_data_dir

        self.assertTrue(result["success"])
        download = result["downloads"][0]
        self.assertEqual(download["source"], "ibge_municipios")
        self.assertTrue(download["sha256"])
        self.assertEqual(manager.mode, "OFFLINE")

    def test_allowed_public_sources_have_https_download_urls(self) -> None:
        for source in allowed_public_sources():
            self.assertTrue(source.download_url.startswith("https://"))

    def test_unknown_source_is_rejected(self) -> None:
        manager = HybridSecurityManager(mode="OFFLINE", enrichment_enabled=True)

        with self.assertRaises(HybridSecurityError):
            manager.run_automatic_downloads(source_keys=["cpf_lookup"])
        self.assertEqual(manager.mode, "OFFLINE")

    def test_sensitive_external_queries_are_cataloged_as_blocked(self) -> None:
        blocked_keys = {item["key"] for item in blocked_external_api_requests()}

        self.assertIn("cpf_lookup", blocked_keys)
        self.assertIn("cep_lookup_from_document", blocked_keys)
        self.assertIn("openai_or_cloud_ai_document_processing", blocked_keys)


if __name__ == "__main__":
    unittest.main()
