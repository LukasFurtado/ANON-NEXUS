import unittest

from app.core.profile_loader import available_profiles, load_profile, profile_context_prompt


class ProfileLoaderTest(unittest.TestCase):
    def test_profiles_are_available(self) -> None:
        profiles = available_profiles()
        self.assertIn("rif", profiles)
        self.assertIn("extrato_bancario", profiles)
        self.assertIn("relatorio_investigativo", profiles)

    def test_profile_prompt_contains_core_sections(self) -> None:
        profile = load_profile("rif")
        prompt = profile_context_prompt("rif")
        self.assertEqual(profile["profile_id"], "rif")
        self.assertIn("Preserve obrigatoriamente", prompt)
        self.assertIn("Anonimize obrigatoriamente", prompt)


if __name__ == "__main__":
    unittest.main()
