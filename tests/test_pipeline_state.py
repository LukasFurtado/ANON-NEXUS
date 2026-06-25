import unittest

from app.core.pipeline_state import PipelineStateEmitter


class PipelineStateTest(unittest.TestCase):
    def test_pipeline_state_records_stages(self) -> None:
        emitter = PipelineStateEmitter("test-pipeline-state")
        emitter.stage_start("parser", "pdf")
        emitter.stage_ok("parser", "texto extraido")
        payload = emitter.finalize()

        self.assertEqual(payload["pipeline_id"], "test-pipeline-state")
        self.assertEqual(payload["overall_status"], "ok")
        self.assertEqual(payload["stages"][0]["name"], "parser")


if __name__ == "__main__":
    unittest.main()
