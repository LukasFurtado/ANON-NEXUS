import json
import unittest

from app.models.schemas import EntityType
from app.pipeline.anonymizer import ReplacementState
from app.pipeline.sync_package import apply_sync_entries_to_state, detect_sync_entities, parse_sync_package


class SyncPackageTest(unittest.TestCase):
    def test_sync_package_loads_entries_and_preserves_marker(self) -> None:
        package = {
            "schema": "ANON-SYNC-PACKAGE-v1",
            "entries": [
                {
                    "original_value": "AYLA DE ARAUJO BESERRA",
                    "entity_type": "PERSON",
                    "anonymous_id": "[PESSOA_123]",
                }
            ],
        }

        entries = parse_sync_package(json.dumps(package).encode("utf-8"), "sync.json")
        state = ReplacementState()
        loaded = apply_sync_entries_to_state(state, entries)
        entities = detect_sync_entities("Consta AYLA DE ARAUJO BESERRA no documento.", entries)

        self.assertEqual(loaded, 1)
        self.assertEqual(entries[0].entity_type, EntityType.person)
        self.assertIn("[PESSOA_123]", state.replacements.values())
        self.assertEqual(state.counters["PESSOA"], 123)
        self.assertEqual(len(entities), 1)
        self.assertEqual(entities[0].text, "AYLA DE ARAUJO BESERRA")

    def test_sync_package_rejects_non_json_files(self) -> None:
        with self.assertRaises(ValueError):
            parse_sync_package(b"ANON - LOG DA REANALISE", "log_reanalise.txt")


if __name__ == "__main__":
    unittest.main()
