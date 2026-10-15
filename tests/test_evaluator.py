"""Unit tests for AlphaEvaluator hurdle logic."""
import unittest
from unittest.mock import MagicMock
from pipeline.config import PipelineConfig
from pipeline.evaluator import AlphaEvaluator

class TestEvaluator(unittest.TestCase):
    def test_evaluator_passing_alpha(self):
        cfg = PipelineConfig()
        mock_client = MagicMock()
        evaluator = AlphaEvaluator(client=mock_client, config=cfg)

        mock_client.run_platform_checks.return_value = {
            "is": {
                "checks": [
                    {"name": "LOW_SHARPE", "result": "PASS", "limit": 1.25, "value": 2.10},
                    {"name": "LOW_FITNESS", "result": "PASS", "limit": 1.00, "value": 1.85},
                    {"name": "SELF_CORRELATION", "result": "PASS", "limit": 0.70, "value": 0.55}
                ],
                "selfCorrelated": {
                    "max": 0.55
                }
            }
        }

        alpha_data = {
            "id": "mock_alpha_123",
            "regular": {"code": "group_neutralize(rank(close), subindustry)"},
            "settings": {"universe": "TOP3000", "decay": 20},
            "is": {
                "sharpe": 2.10,
                "fitness": 1.85,
                "turnover": 0.14,
                "returns": 0.12,
                "drawdown": 0.05,
                "margin": 0.0015
            }
        }

        result = evaluator.evaluate_alpha(alpha_data)
        self.assertTrue(result.is_submittable)
        self.assertEqual(result.max_self_correlation, 0.55)
        self.assertEqual(len(result.fail_reasons), 0)

    def test_evaluator_failing_correlation(self):
        cfg = PipelineConfig()
        mock_client = MagicMock()
        evaluator = AlphaEvaluator(client=mock_client, config=cfg)

        mock_client.run_platform_checks.return_value = {
            "is": {
                "checks": [
                    {"name": "LOW_SHARPE", "result": "PASS", "limit": 1.25, "value": 2.10},
                    {"name": "LOW_FITNESS", "result": "PASS", "limit": 1.00, "value": 1.85},
                    {"name": "SELF_CORRELATION", "result": "FAIL", "limit": 0.70, "value": 0.88}
                ],
                "selfCorrelated": {
                    "max": 0.88
                }
            }
        }

        alpha_data = {
            "id": "mock_alpha_456",
            "regular": {"code": "group_neutralize(rank(close), subindustry)"},
            "settings": {"universe": "TOP3000", "decay": 20},
            "is": {
                "sharpe": 2.10,
                "fitness": 1.85,
                "turnover": 0.14
            }
        }

        result = evaluator.evaluate_alpha(alpha_data)
        self.assertFalse(result.is_submittable)
        self.assertEqual(result.max_self_correlation, 0.88)
        self.assertTrue(any("SELF_CORRELATION" in reason for reason in result.fail_reasons))

    def test_evaluator_with_alpha_id_string_and_db(self):
        cfg = PipelineConfig()
        mock_client = MagicMock()
        mock_db = MagicMock()
        evaluator = AlphaEvaluator(client=mock_client, config=cfg, db=mock_db)

        alpha_data = {
            "id": "mock_alpha_789",
            "regular": {"code": "group_neutralize(rank(close), subindustry)"},
            "settings": {"universe": "TOP3000", "decay": 20},
            "is": {
                "sharpe": 2.20,
                "fitness": 1.90,
                "turnover": 0.15,
                "returns": 0.14,
                "drawdown": 0.04,
                "margin": 0.0020
            }
        }
        mock_client.fetch_alpha.return_value = alpha_data
        mock_client.run_platform_checks.return_value = {
            "is": {
                "checks": [
                    {"name": "LOW_SHARPE", "result": "PASS", "limit": 1.25, "value": 2.20},
                    {"name": "LOW_FITNESS", "result": "PASS", "limit": 1.00, "value": 1.90},
                    {"name": "SELF_CORRELATION", "result": "PASS", "limit": 0.70, "value": 0.40}
                ],
                "selfCorrelated": {"max": 0.40}
            }
        }

        # Test evaluating via string ID
        res = evaluator.evaluate_alpha("mock_alpha_789")
        self.assertEqual(res.id, "mock_alpha_789")
        self.assertTrue(res.is_submittable)
        mock_client.fetch_alpha.assert_called_once_with("mock_alpha_789")
        mock_db.save_evaluation.assert_called_once()

if __name__ == "__main__":
    unittest.main()
