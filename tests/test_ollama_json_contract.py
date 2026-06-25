import unittest
import sys
import types
from unittest.mock import patch

from app.models.schemas import DocumentKind, EntityType

if "pydantic_settings" not in sys.modules:
    shim = types.ModuleType("pydantic_settings")
    shim.BaseSettings = object
    sys.modules["pydantic_settings"] = shim

from app.services import ollama


class OllamaJsonContractTest(unittest.TestCase):
    def test_contract_accepts_actions_and_ignores_preserve_items(self) -> None:
        text = "Joao Silva fez transferencia no Banco do Brasil."
        raw = (
            '{"entities":['
            '{"type":"PESSOA","text":"Joao Silva","action":"anonimizar","start":0,"end":10},'
            '{"type":"ORGANIZATION","text":"Banco do Brasil","action":"preserve","start":31,"end":46}'
            ']}'
        )

        with patch.object(ollama, "_request_ollama_generate", return_value=raw):
            result = ollama._detect_entities_with_ollama_chunk(text, 0, "qwen3:32b", DocumentKind.rif)

        self.assertEqual(len(result.entities), 1)
        self.assertEqual(result.entities[0].type, EntityType.person)
        self.assertEqual(result.entities[0].text, "Joao Silva")
        self.assertEqual(result.json_rejected_chunks, 0)

    def test_contract_accepts_review_action_as_candidate(self) -> None:
        text = "Chave PIX joao@email.com."
        raw = '{"entities":[{"tipo":"PIX","valor":"joao@email.com","acao":"revisar"}]}'

        with patch.object(ollama, "_request_ollama_generate", return_value=raw):
            result = ollama._detect_entities_with_ollama_chunk(text, 0, "qwen3:32b", DocumentKind.rif)

        self.assertEqual(len(result.entities), 1)
        self.assertEqual(result.entities[0].type, EntityType.pix)
        self.assertEqual(result.entities[0].text, "joao@email.com")

    def test_contract_accepts_confidence_reason_and_top_level_preserve(self) -> None:
        text = "JOAO SILVA transferiu para Banco do Brasil."
        raw = (
            '{"entities":[{"type":"PERSON","text":"JOAO SILVA","start":0,"end":10,'
            '"action":"anonymize","reason":"nome de pessoa fisica","confidence":0.97}],'
            '"preserve":[{"text":"Banco do Brasil","reason":"instituicao operacional"}]}'
        )

        with patch.object(ollama, "_request_ollama_generate", return_value=raw):
            result = ollama._detect_entities_with_ollama_chunk(text, 0, "qwen3:32b", DocumentKind.rif)

        self.assertEqual(len(result.entities), 1)
        self.assertEqual(result.entities[0].text, "JOAO SILVA")
        self.assertEqual(result.entities[0].confidence, 0.97)
        self.assertEqual(result.entities[0].reason, "nome de pessoa fisica")
        self.assertEqual(result.entities[0].action, "anonymize")
        self.assertEqual(result.preserved_items, 1)


if __name__ == "__main__":
    unittest.main()
