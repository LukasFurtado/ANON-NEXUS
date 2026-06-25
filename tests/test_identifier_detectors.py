import unittest

from app.models.schemas import DocumentKind, Entity, EntityType
from app.pipeline.identifier_detectors import (
    detect_structured_identifiers,
    is_possible_truncated_cpf_digits,
    is_protected_institution,
    is_valid_cnpj_digits,
    is_valid_cpf_digits,
)
from app.pipeline.validator import validate_entities


class IdentifierDetectorsTest(unittest.TestCase):
    def test_cpf_detector_validates_multiple_formats(self) -> None:
        text = "CPF 123.456.789-09 e CPF 012345678909 foram informados. CPF 111.111.111-11 deve cair."
        entities = detect_structured_identifiers(text)
        cpfs = [entity.text for entity in entities if entity.type == EntityType.cpf]

        self.assertIn("123.456.789-09", cpfs)
        self.assertIn("012345678909", cpfs)
        self.assertNotIn("111.111.111-11", cpfs)
        self.assertTrue(is_valid_cpf_digits("12345678909"))
        self.assertFalse(is_valid_cpf_digits("11111111111"))

    def test_cpf_detector_flags_missing_leading_zero_in_context(self) -> None:
        text = "CPF 001.234.567-97 e CPF 0123456797 foram exportados na mesma linha."
        entities = detect_structured_identifiers(text)
        cpfs = [entity.text for entity in entities if entity.type == EntityType.cpf]

        self.assertIn("001.234.567-97", cpfs)
        self.assertIn("0123456797", cpfs)
        self.assertTrue(is_possible_truncated_cpf_digits("0123456797"))

    def test_cnpj_detector_validates_digits(self) -> None:
        text = "CNPJ 11.222.333/0001-81 e 00.000.000/0000-00."
        entities = detect_structured_identifiers(text)
        cnpjs = [entity.text for entity in entities if entity.type == EntityType.cnpj]

        self.assertIn("11.222.333/0001-81", cnpjs)
        self.assertNotIn("00.000.000/0000-00", cnpjs)
        self.assertTrue(is_valid_cnpj_digits("11222333000181"))

    def test_phone_detector_uses_brazilian_ddd_rules(self) -> None:
        text = "WhatsApp (81) 98765-4321, fixo 81 3456-7890 e numero 10 98765-4321."
        entities = detect_structured_identifiers(text)
        phones = [entity.text for entity in entities if entity.type == EntityType.phone]

        self.assertIn("(81) 98765-4321", phones)
        self.assertIn("81 3456-7890", phones)
        self.assertNotIn("10 98765-4321", phones)

    def test_bank_contextual_detector(self) -> None:
        text = "Agencia: 1234 Conta 987654-0. Banco 001 Agencia 4321 Conta 123456789."
        entities = detect_structured_identifiers(text)
        types = {entity.type for entity in entities}

        self.assertIn(EntityType.bank_branch, types)
        self.assertIn(EntityType.bank_account, types)

    def test_name_library_detects_contextual_brazilian_names(self) -> None:
        text = "A vitima Maria Oliveira relatou fatos contra o investigado Beatriz Rodrigues."
        entities = detect_structured_identifiers(text)
        names = [entity.text for entity in entities if entity.type == EntityType.person]

        self.assertIn("Maria Oliveira", names)
        self.assertIn("Beatriz Rodrigues", names)

    def test_institutional_library_preserves_public_entities(self) -> None:
        text = "Banco do Brasil informou CPF 123.456.789-09."
        start = text.index("Banco")
        entities = [
            Entity(type=EntityType.organization, text="Banco do Brasil", start=start, end=start + len("Banco do Brasil"), source="test")
        ]

        valid, _, _, warnings = validate_entities(text, entities, DocumentKind.rif)

        self.assertEqual(valid, [])
        self.assertTrue(is_protected_institution("Banco do Brasil"))
        self.assertTrue(any("biblioteca institucional" in warning or "entidade publica" in warning for warning in warnings))

    def test_institutional_library_does_not_preserve_full_address(self) -> None:
        self.assertTrue(is_protected_institution("BANCO DO BRASIL S.A."))
        self.assertTrue(is_protected_institution("Policia Civil de Pernambuco"))
        self.assertFalse(is_protected_institution("Rua das Flores, 100, Recife PE"))


if __name__ == "__main__":
    unittest.main()
