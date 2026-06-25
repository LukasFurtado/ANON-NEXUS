import unittest

from app.core.profile_loader import profile_context_prompt
from app.models.schemas import DocumentKind, EntityType
from app.pipeline.delos_rules import should_preserve_entity
from app.services.knowledge_base import compact_profile_guidance


class DelosReverseEngineeringTest(unittest.TestCase):
    def test_delos_rules_reach_profile_prompt(self) -> None:
        prompt = profile_context_prompt(DocumentKind.extrato_bancario.value)

        self.assertIn("Engenharia reversa DELOS ativa", prompt)
        self.assertIn("Doc.", prompt)
        self.assertIn("DOCUMENTO EXIGE RECUPERACAO MANUAL", prompt)

    def test_delos_rules_reach_compact_knowledge_prompt(self) -> None:
        guidance = compact_profile_guidance(DocumentKind.extrato_bancario)

        self.assertIn("ENGENHARIA REVERSA DELOS", guidance)
        self.assertIn("Doc.", guidance)
        self.assertIn("Observacoes", guidance)

    def test_delos_preserves_operational_notice(self) -> None:
        preserve, reason = should_preserve_entity(
            "DOCUMENTO EXIGE RECUPERACAO MANUAL",
            "CRED.AUTOR DOCUMENTO EXIGE RECUPERACAO MANUAL",
            EntityType.person,
        )

        self.assertTrue(preserve)
        self.assertIn("historico bancario", reason)


if __name__ == "__main__":
    unittest.main()
