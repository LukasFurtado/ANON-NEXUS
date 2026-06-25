import unittest

from app.services.system_metrics import collect_system_metrics


class SystemMetricsTest(unittest.TestCase):
    def test_collect_system_metrics_has_stable_sections(self) -> None:
        metrics = collect_system_metrics()

        self.assertIn("cpu", metrics)
        self.assertIn("memory", metrics)
        self.assertIn("gpu", metrics)
        self.assertIn("available", metrics["cpu"])
        self.assertIn("percent", metrics["cpu"])
        self.assertIn("available", metrics["memory"])
        self.assertIn("percent", metrics["memory"])
        self.assertIn("available", metrics["gpu"])
        self.assertIn("label", metrics["gpu"])


if __name__ == "__main__":
    unittest.main()
