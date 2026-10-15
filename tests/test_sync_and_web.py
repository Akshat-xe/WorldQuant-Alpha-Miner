import unittest
from unittest.mock import MagicMock
import tempfile
import os
import asyncio

from pipeline.database import AlphaDatabase
from pipeline.config import PipelineConfig
from pipeline.client import BrainClient
from web.server import get_stats, get_alphas, get_active_portfolio

class TestSyncAndDatabase(unittest.TestCase):
    def setUp(self):
        self.temp_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.temp_db_path = self.temp_file.name
        self.temp_file.close()
        self.db = AlphaDatabase(self.temp_db_path)

    def tearDown(self):
        if os.path.exists(self.temp_db_path):
            os.remove(self.temp_db_path)

    def test_save_cloud_alpha_active(self):
        sample_active = {
            "id": "alpha_active_test_01",
            "status": "ACTIVE",
            "regular": {"code": "rank(sales / cap)"},
            "settings": {
                "region": "USA",
                "universe": "TOP3000",
                "delay": 1,
                "decay": 20,
                "neutralization": "SUBINDUSTRY"
            },
            "is": {
                "sharpe": 2.15,
                "fitness": 2.65,
                "turnover": 0.12,
                "returns": 0.18,
                "drawdown": 0.05,
                "margin": 0.0015,
                "checks": [{"name": "LOW_SHARPE", "result": "PASS", "value": 2.15}]
            }
        }
        res = self.db.save_cloud_alpha(sample_active)
        self.assertTrue(res)

        saved = self.db.get_alpha("alpha_active_test_01")
        self.assertIsNotNone(saved)
        self.assertEqual(saved["submission_status"], "SUBMITTED")
        self.assertEqual(saved["is_submittable"], 1)
        self.assertEqual(saved["sharpe"], 2.15)
        self.assertEqual(saved["fitness"], 2.65)

    def test_save_cloud_alpha_unsubmitted(self):
        sample_unsub = {
            "id": "alpha_unsub_test_02",
            "status": "UNSUBMITTED",
            "regular": {"code": "rank(operating_income / assets)"},
            "settings": {
                "region": "USA",
                "universe": "TOP1000",
                "delay": 0,
                "decay": 15,
                "neutralization": "NONE"
            },
            "is": {
                "sharpe": 1.45,
                "fitness": 1.12,
                "turnover": 0.25,
                "returns": 0.08,
                "drawdown": 0.10,
                "margin": 0.0008,
                "checks": [{"name": "LOW_SHARPE", "result": "PASS", "value": 1.45}]
            }
        }
        res = self.db.save_cloud_alpha(sample_unsub)
        self.assertTrue(res)

        saved = self.db.get_alpha("alpha_unsub_test_02")
        self.assertIsNotNone(saved)
        self.assertEqual(saved["submission_status"], "UNSUBMITTED")
        self.assertEqual(saved["is_submittable"], 1)

    def test_db_stats_calculation(self):
        self.db.save_cloud_alpha({
            "id": "alpha_spec",
            "status": "ACTIVE",
            "regular": {"code": "x"},
            "is": {"sharpe": 2.5, "fitness": 2.8, "returns": 0.22, "drawdown": 0.04}
        })
        self.db.save_cloud_alpha({
            "id": "alpha_draft",
            "status": "UNSUBMITTED",
            "regular": {"code": "y"},
            "is": {"sharpe": 1.1, "fitness": 0.8, "returns": 0.05, "drawdown": 0.12}
        })

        stats = self.db.get_stats()
        self.assertEqual(stats["total"], 2)
        self.assertEqual(stats["active"], 1)
        self.assertEqual(stats["unsubmitted"], 1)
        self.assertEqual(stats["spectacular"], 1)
        self.assertEqual(stats["leader_id"], "alpha_spec")
        self.assertEqual(stats["leader_fitness"], 2.8)

    def test_sync_user_alphas_with_mock(self):
        client = BrainClient.__new__(BrainClient)
        client.config = PipelineConfig()
        client.fetch_alphas = MagicMock(side_effect=[
            {"count": 1, "results": [{"id": "cloud_active_1", "status": "ACTIVE", "regular": {"code": "c1"}, "is": {"sharpe": 2.0, "fitness": 2.1}}]},
            {"count": 1, "results": [{"id": "cloud_unsub_1", "status": "UNSUBMITTED", "regular": {"code": "c2"}, "is": {"sharpe": 1.3, "fitness": 1.1}}]}
        ])

        sync_res = client.sync_user_alphas(self.db, max_unsubmitted=10)
        self.assertTrue(sync_res["success"])
        self.assertEqual(sync_res["active_synced"], 1)
        self.assertEqual(sync_res["unsubmitted_synced"], 1)
        self.assertEqual(sync_res["total_synced"], 2)

        self.assertEqual(self.db.count_alphas(), 2)
        self.assertIsNotNone(self.db.get_alpha("cloud_active_1"))
        self.assertIsNotNone(self.db.get_alpha("cloud_unsub_1"))

    def test_update_correlation_result_fail_removes_submittable(self):
        # Insert initially submittable unsubmitted alpha
        self.db.save_cloud_alpha({
            "id": "candidate_alpha_01",
            "status": "UNSUBMITTED",
            "regular": {"code": "rank(volume)"},
            "is": {"sharpe": 1.8, "fitness": 1.6, "turnover": 0.15, "checks": []}
        })
        alpha = self.db.get_alpha("candidate_alpha_01")
        self.assertEqual(alpha["is_submittable"], 1)

        # Correlation check fails (max 0.85 >= 0.70)
        self.db.update_correlation_result("candidate_alpha_01", max_correlation=0.85, passed=False)

        updated = self.db.get_alpha("candidate_alpha_01")
        self.assertEqual(updated["is_submittable"], 0)
        self.assertEqual(updated["max_self_correlation"], 0.85)
        self.assertEqual(updated["correlation_checked"], 1)
        self.assertTrue(any("SELF_CORRELATION" in reason for reason in updated["fail_reasons"]))

    def test_update_correlation_result_pass_preserves_submittable(self):
        self.db.save_cloud_alpha({
            "id": "candidate_alpha_02",
            "status": "UNSUBMITTED",
            "regular": {"code": "rank(vwap)"},
            "is": {"sharpe": 2.1, "fitness": 2.2, "turnover": 0.10, "checks": []}
        })
        # Passes correlation (0.45 < 0.70)
        self.db.update_correlation_result("candidate_alpha_02", max_correlation=0.45, passed=True)

        updated = self.db.get_alpha("candidate_alpha_02")
        self.assertEqual(updated["is_submittable"], 1)
        self.assertEqual(updated["max_self_correlation"], 0.45)
        self.assertEqual(updated["correlation_checked"], 1)

    def test_get_unchecked_unsubmitted_alphas_skips_checked(self):
        self.db.save_cloud_alpha({
            "id": "alpha_uncheck_1",
            "status": "UNSUBMITTED",
            "regular": {"code": "rank(a)"},
            "is": {"sharpe": 1.5, "fitness": 1.5, "turnover": 0.10}
        })
        self.db.save_cloud_alpha({
            "id": "alpha_uncheck_2",
            "status": "UNSUBMITTED",
            "regular": {"code": "rank(b)"},
            "is": {"sharpe": 1.9, "fitness": 2.0, "turnover": 0.10}
        })

        unchecked = self.db.get_unchecked_unsubmitted_alphas()
        self.assertEqual(len(unchecked), 2)
        # Should prioritize highest fitness/submittable
        self.assertEqual(unchecked[0]["id"], "alpha_uncheck_2")

        # Mark alpha_uncheck_2 as checked
        self.db.update_correlation_result("alpha_uncheck_2", max_correlation=0.3, passed=True)

        unchecked_after = self.db.get_unchecked_unsubmitted_alphas()
        self.assertEqual(len(unchecked_after), 1)
        self.assertEqual(unchecked_after[0]["id"], "alpha_uncheck_1")

    def test_db_stats_today_only(self):
        # Insert an alpha dated today
        self.db.save_evaluation({
            "id": "alpha_today_01",
            "expression": "rank(close)",
            "sharpe": 2.1,
            "fitness": 2.2,
            "returns": 0.15,
            "turnover": 0.20,
            "margin": 0.0012,
            "drawdown": 0.05,
            "is_submittable": True,
            "status": "SUBMITTED"
        })
        # Check today stats returns at least this alpha
        today_stats = self.db.get_stats(today_only=True)
        self.assertGreaterEqual(today_stats["total"], 1)
        self.assertGreaterEqual(today_stats["active"], 1)
        self.assertTrue(today_stats["is_today_only"])

class TestWebEndpoints(unittest.TestCase):
    def test_api_stats_endpoint(self):
        mock_req = MagicMock()
        mock_req.cookies = {}
        res = asyncio.run(get_stats(mock_req))
        self.assertIn("total", res)
        self.assertIn("submittable", res)
        self.assertIn("active", res)

        # Test with today_only=True
        res_today = asyncio.run(get_stats(mock_req, today_only=True))
        self.assertIn("total", res_today)
        self.assertTrue(res_today["is_today_only"])

    def test_api_alphas_filters(self):
        mock_req = MagicMock()
        mock_req.cookies = {}
        res_unsub = asyncio.run(get_alphas(mock_req, unsubmitted_only=True))
        self.assertIn("alphas", res_unsub)

        res_active = asyncio.run(get_alphas(mock_req, active_only=True))
        self.assertIn("alphas", res_active)

        res_submittable = asyncio.run(get_alphas(mock_req, submittable_only=True))
        self.assertIn("alphas", res_submittable)

        res_today = asyncio.run(get_alphas(mock_req, today_only=True))
        self.assertIn("alphas", res_today)

    def test_api_correlation_worker_status_endpoint(self):
        from web.server import get_correlation_worker_status
        mock_req = MagicMock()
        mock_req.cookies = {}
        res = asyncio.run(get_correlation_worker_status(mock_req))
        self.assertIn("is_running", res)
        self.assertIn("is_paused", res)
        self.assertIn("checked_count", res)

if __name__ == "__main__":
    unittest.main()

