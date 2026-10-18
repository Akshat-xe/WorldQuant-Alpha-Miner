import unittest
from unittest.mock import MagicMock
from pipeline.engine_algorithmic import AlgorithmicEngine
from pipeline.closed_loop_optimizer import ClosedLoopStudioOptimizer
from pipeline.config import PipelineConfig

class TestClosedLoopOptimizer(unittest.TestCase):

    def test_mutate_turnover_failure(self):
        candidate = {
            "name": "TestAlpha",
            "expr": "reversal = rank(-returns);\ngroup_neutralize(reversal, subindustry)",
            "decay": 8,
            "universe": "TOP3000",
            "neutralization": "SUBINDUSTRY"
        }
        eval_data = {
            "metrics": {"sharpe": 1.45, "turnover": 0.85, "fitness": 1.5, "self_corr": 0.40},
            "hurdle_failures": ["Turnover 0.8500 > max 0.7000"]
        }
        res = AlgorithmicEngine.mutate_and_improve(candidate, eval_data)
        mutated = res["candidate"]
        
        self.assertGreater(mutated["decay"], 8)
        self.assertIn("ts_mean(-returns, 3)", mutated["expr"])
        self.assertIn("decay", res["actions_summary"].lower())

    def test_mutate_sharpe_failure(self):
        candidate = {
            "name": "TestAlpha",
            "expr": "group_neutralize(rank(close - open), subindustry)",
            "decay": 12,
            "universe": "TOP3000",
            "neutralization": "SUBINDUSTRY"
        }
        eval_data = {
            "metrics": {"sharpe": 0.95, "turnover": 0.25, "fitness": 0.80, "self_corr": 0.35},
            "hurdle_failures": ["Sharpe 0.95 < min required 1.25"]
        }
        res = AlgorithmicEngine.mutate_and_improve(candidate, eval_data)
        mutated = res["candidate"]
        
        self.assertIn("power(", mutated["expr"])
        self.assertIn("power", res["actions_summary"].lower())

    def test_mutate_correlation_failure(self):
        candidate = {
            "name": "TestAlpha",
            "expr": "group_neutralize(fast_trend, subindustry)",
            "decay": 14,
            "universe": "TOP3000",
            "neutralization": "SUBINDUSTRY"
        }
        eval_data = {
            "metrics": {"sharpe": 1.50, "turnover": 0.30, "fitness": 1.6, "self_corr": 0.76},
            "hurdle_failures": ["Self-correlation 0.7600 > limit 0.7000"]
        }
        res = AlgorithmicEngine.mutate_and_improve(candidate, eval_data)
        mutated = res["candidate"]
        
        self.assertEqual(mutated["neutralization"], "SECTOR")
        self.assertIn("sector", mutated["expr"].lower())

    def test_optimizer_session_execution(self):
        mock_client = MagicMock()
        # Mock simulation returns
        mock_client.simulate_candidate.return_value = {
            "id": "sim_alpha_123",
            "settings": {"region": "USA", "universe": "TOP3000", "delay": 1, "decay": 14, "neutralization": "SUBINDUSTRY"},
            "regular": {"code": "rank(-returns)"},
            "is": {
                "sharpe": 1.62,
                "fitness": 1.55,
                "turnover": 0.28,
                "returns": 0.18,
                "drawdown": 0.08,
                "margin": 0.0035,
                "checks": [{"name": "SHARPE", "result": "PASS", "value": 1.62, "limit": 1.25}]
            }
        }
        mock_client.run_platform_checks.return_value = {
            "is": {
                "checks": [{"name": "SELF_CORRELATION", "result": "PASS", "value": 0.42, "limit": 0.70}],
                "selfCorrelated": {"max": 0.42}
            }
        }

        candidate = {
            "name": "InitialIdea",
            "expr": "rank(-returns)",
            "decay": 14,
            "universe": "TOP3000",
            "neutralization": "SUBINDUSTRY"
        }

        session_id = ClosedLoopStudioOptimizer.start_session(
            initial_candidate=candidate,
            client=mock_client,
            db=None,
            max_iterations=3,
            target_sharpe=1.25
        )

        # Wait briefly for thread to process mock
        import time
        time.sleep(1.5)

        session = ClosedLoopStudioOptimizer.get_session(session_id)
        self.assertIsNotNone(session)
        self.assertTrue(session["is_submittable"])
        self.assertEqual(session["status"], "SUBMITTABLE")
        self.assertEqual(session["submittable_alpha_id"], "sim_alpha_123")
        self.assertGreaterEqual(len(session["steps"]), 1)

if __name__ == "__main__":
    unittest.main()
