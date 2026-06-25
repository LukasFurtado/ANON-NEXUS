import re
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from app.models.schemas import AnonymizeOptions, DocumentKind

if "pydantic_settings" not in sys.modules:
    shim = types.ModuleType("pydantic_settings")
    shim.BaseSettings = object
    sys.modules["pydantic_settings"] = shim

from app.pipeline.runner import run_batch_pipeline, run_pipeline
from app.services.ollama import OllamaDetectionError, OllamaDetectionResult


class PriorityFallbackAndControlledCorpusTest(unittest.TestCase):
    def test_ollama_failure_uses_auditable_local_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "relatorio.txt"
            path.write_text(
                "JOAO CARLOS DA SILVA CPF 111.444.777-35 reside na Rua das Flores, 100.",
                encoding="utf-8",
            )
            options = AnonymizeOptions(document_kind=DocumentKind.rif, model="qwen3:32b", use_ollama=True)

            with (
                patch(
                    "app.pipeline.runner.detect_entities_with_ollama",
                    side_effect=OllamaDetectionError("Ollama local nao respondeu."),
                ),
                patch("app.pipeline.runner.save_job"),
            ):
                result = run_pipeline(path, path.name, options)

        self.assertGreater(result.stats.replacements_applied, 0)
        self.assertIn("[CPF_001]", result.anonymized_text)
        self.assertNotIn("111.444.777-35", result.anonymized_text)
        self.assertEqual(result.stats.ollama_failure_reason, "Ollama local nao respondeu.")
        self.assertTrue(any("IA local foi acionada" in warning for warning in result.stats.validation_warnings))
        self.assertEqual(result.pipeline_state["overall_status"], "warn")

    def test_controlled_rif_corpus_keeps_identity_consistent_across_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            envolvidos = root / "RIF138538_Envolvidos.csv"
            comunicacoes = root / "RIF138538_Comunicacoes.csv"
            ocorrencias = root / "RIF138538_Ocorrencias.csv"
            envolvidos.write_text(
                "Indexador;cpfCnpjEnvolvido;nomeEnvolvido;tipoEnvolvido;agenciaEnvolvido;contaEnvolvido\n"
                "1;11144477735;JOAO CARLOS DA SILVA;Titular;1234;98765-0\n",
                encoding="utf-8",
            )
            comunicacoes.write_text(
                "Indexador;idComunicacao;NumeroOcorrenciaBC;Data_do_Recebimento;Data_da_operacao;"
                "cpfCnpjComunicante;nomeComunicante;informacoesAdicionais;CodigoSegmento\n"
                "1;777;888;01/02/2024;02/02/2024;191;BANCO DO BRASIL SA;"
                "Transferencia realizada por JOAO CARLOS DA SILVA CPF 11144477735 para MARIA OLIVEIRA CPF 98765432100;1\n",
                encoding="utf-8",
            )
            ocorrencias.write_text(
                "Indexador;idOcorrencia;Ocorrencia\n"
                "1;204;Depositos em especie fracionados em valores inferiores ao limite operacional\n",
                encoding="utf-8",
            )
            options = AnonymizeOptions(
                document_kind=DocumentKind.rif,
                model="qwen3:32b",
                use_ollama=True,
                request_title="Corpus controlado RIF",
            )

            with (
                patch(
                    "app.pipeline.runner.detect_entities_with_ollama",
                    return_value=OllamaDetectionResult(entities=[]),
                ),
                patch("app.pipeline.runner.save_job"),
            ):
                batch = run_batch_pipeline(
                    [
                        (envolvidos, envolvidos.name),
                        (comunicacoes, comunicacoes.name),
                        (ocorrencias, ocorrencias.name),
                    ],
                    options,
                )

        self.assertEqual(len(batch.results), 3)
        envolvidos_result = batch.results[0]
        comunicacoes_result = batch.results[1]
        ocorrencias_result = batch.results[2]

        pessoa_envolvidos = set(re.findall(r"\[PESSOA_\d{3}\]", envolvidos_result.anonymized_text))
        pessoa_comunicacoes = set(re.findall(r"\[PESSOA_\d{3}\]", comunicacoes_result.anonymized_text))
        cpf_envolvidos = set(re.findall(r"\[CPF_\d{3}\]", envolvidos_result.anonymized_text))
        cpf_comunicacoes = set(re.findall(r"\[CPF_\d{3}\]", comunicacoes_result.anonymized_text))

        self.assertIn("[PESSOA_001]", pessoa_envolvidos)
        self.assertIn("[PESSOA_001]", pessoa_comunicacoes)
        self.assertIn("[CPF_001]", cpf_envolvidos)
        self.assertIn("[CPF_001]", cpf_comunicacoes)
        self.assertNotIn("JOAO CARLOS DA SILVA", envolvidos_result.anonymized_text)
        self.assertNotIn("11144477735", comunicacoes_result.anonymized_text)
        self.assertIn("Depositos em especie fracionados", ocorrencias_result.anonymized_text)
        self.assertLessEqual(len(batch.results), 3)

    def test_controlled_bank_statement_corpus_preserves_operational_fields(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "extrato_controlado.txt"
            path.write_text(
                "Titular: ALINE MARIA DE SOUZA (CPF/CNPJ: 11144477735)\n"
                "Data Doc. Historico Valor\n"
                "01/01/2024 123 PAGTO CARTAO CREDITO 100,00\n"
                "C 98765432100 MARIA OLIVEIRA TRANSFERENCIA PIX 500,00\n",
                encoding="utf-8",
            )
            options = AnonymizeOptions(
                document_kind=DocumentKind.extrato_bancario,
                model="qwen3:32b",
                use_ollama=True,
                request_title="Corpus controlado extrato bancario",
            )

            with (
                patch(
                    "app.pipeline.runner.detect_entities_with_ollama",
                    return_value=OllamaDetectionResult(entities=[]),
                ),
                patch("app.pipeline.runner.save_job"),
            ):
                result = run_pipeline(path, path.name, options)

        self.assertNotIn("ALINE MARIA DE SOUZA", result.anonymized_text)
        self.assertNotIn("11144477735", result.anonymized_text)
        self.assertIn("Doc.", result.anonymized_text)
        self.assertIn("123", result.anonymized_text)
        self.assertIn("PAGTO CARTAO CREDITO", result.anonymized_text)
        self.assertIn("100,00", result.anonymized_text)

    def test_controlled_rif_pix_narrative_preserves_operation_text(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "rif_narrativo.txt"
            path.write_text(
                "JOAO CARLOS DA SILVA, CPF 111.444.777-35, realizou transferencia PIX para "
                "MARIA OLIVEIRA, CPF 935.411.347-80, no valor de R$ 15.000,00.",
                encoding="utf-8",
            )
            options = AnonymizeOptions(document_kind=DocumentKind.rif, model="qwen3:32b", use_ollama=True)

            with (
                patch(
                    "app.pipeline.runner.detect_entities_with_ollama",
                    return_value=OllamaDetectionResult(entities=[]),
                ),
                patch("app.pipeline.runner.save_job"),
            ):
                result = run_pipeline(path, path.name, options)

        self.assertIn("realizou transferencia PIX para", result.anonymized_text)
        self.assertIn("no valor de R$ 15.000,00", result.anonymized_text)
        self.assertNotIn("MARIA OLIVEIRA", result.anonymized_text)
        self.assertNotIn("935.411.347-80", result.anonymized_text)

    def test_controlled_investigative_report_handles_contact_and_address(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "relatorio_investigativo.txt"
            path.write_text(
                "Investigado: CARLOS EDUARDO LIMA. Telefone: (81) 99999-9999. "
                "E-mail: carlos.lima@example.com. Residente na Rua das Flores, 100. "
                "Processo 0001234-56.2024.8.17.0001 deve ser preservado como referencia processual.",
                encoding="utf-8",
            )
            options = AnonymizeOptions(
                document_kind=DocumentKind.relatorio_investigativo,
                model="qwen3:32b",
                use_ollama=True,
            )

            with (
                patch(
                    "app.pipeline.runner.detect_entities_with_ollama",
                    return_value=OllamaDetectionResult(entities=[]),
                ),
                patch("app.pipeline.runner.save_job"),
            ):
                result = run_pipeline(path, path.name, options)

        self.assertNotIn("CARLOS EDUARDO LIMA", result.anonymized_text)
        self.assertNotIn("(81) 99999-9999", result.anonymized_text)
        self.assertNotIn("carlos.lima@example.com", result.anonymized_text)
        self.assertNotIn("0001234-56.2024.8.17.0001", result.anonymized_text)
        self.assertRegex(result.anonymized_text, r"\[(?:PROCESSO|PROTOCOLO)_001\]")


if __name__ == "__main__":
    unittest.main()
