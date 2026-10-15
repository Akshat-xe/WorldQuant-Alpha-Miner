"""Unit tests for AlgorithmicEngine and AlphaFactory."""
import unittest
from pipeline.engine_algorithmic import AlgorithmicEngine
from pipeline.alpha_factory import AlphaFactory

from unittest.mock import patch, MagicMock
from pipeline.engine_ai import CloudAIEngine

class TestEngines(unittest.TestCase):
    def test_algorithmic_engine_generate_candidate(self):
        cand = AlgorithmicEngine.generate_candidate()
        self.assertIsInstance(cand, dict)
        self.assertIn("name", cand)
        self.assertIn("expr", cand)
        self.assertIn("region", cand)
        self.assertIn("universe", cand)
        self.assertIn("delay", cand)
        self.assertIn("decay", cand)
        self.assertEqual(cand["region"], "USA")
        self.assertIn(cand["delay"], (0, 1))
        self.assertIn("group_neutralize", cand["expr"])

    def test_alpha_factory_complex_candidates(self):
        candidates = AlphaFactory.get_complex_candidates()
        self.assertIsInstance(candidates, list)
        self.assertGreater(len(candidates), 0)
        for c in candidates:
            self.assertIn("name", c)
            self.assertIn("expr", c)
            self.assertIn("decay", c)
            self.assertIn("group_neutralize", c["expr"])

    def test_cloud_ai_engine_default_gemini_requires_key(self):
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(ValueError):
                CloudAIEngine.generate_alpha()  # defaults to gemini

    @patch("pipeline.engine_ai.requests.post")
    def test_cloud_ai_engine_mock_gemini(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {"text": "group_neutralize(rank(cashflow_op / cap) * rank(-returns), subindustry)"}
                        ]
                    }
                }
            ]
        }
        mock_post.return_value = mock_resp

        res = CloudAIEngine.generate_alpha(api_key="mock_gemini_key")
        self.assertEqual(res["engine"], "ai_gemini")
        self.assertIn("group_neutralize", res["expr"])
        self.assertEqual(res["universe"], "TOP3000")

if __name__ == "__main__":
    unittest.main()

