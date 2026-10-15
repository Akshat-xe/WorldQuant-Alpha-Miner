"""Unit tests for PipelineConfig."""
import unittest
from pipeline.config import PipelineConfig

class TestPipelineConfig(unittest.TestCase):
    def test_default_platform_hurdles(self):
        cfg = PipelineConfig()
        self.assertEqual(cfg.min_sharpe, 1.25)
        self.assertEqual(cfg.min_fitness, 1.00)
        self.assertEqual(cfg.min_turnover, 0.01)
        self.assertEqual(cfg.max_turnover, 0.70)
        self.assertEqual(cfg.max_self_correlation, 0.70)

    def test_default_simulation_settings(self):
        cfg = PipelineConfig()
        self.assertEqual(cfg.default_region, "USA")
        self.assertEqual(cfg.default_universe, "TOP3000")
        self.assertEqual(cfg.default_delay, 1)
        self.assertEqual(cfg.default_decay, 10)
        self.assertEqual(cfg.default_language, "FASTEXPR")
        self.assertEqual(cfg.default_truncation, 0.08)
        self.assertEqual(cfg.default_pasteurization, "ON")
        self.assertEqual(cfg.default_unit_handling, "VERIFY")

if __name__ == "__main__":
    unittest.main()
