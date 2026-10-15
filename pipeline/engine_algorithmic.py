"""
Algorithmic Alpha Engine (No AI)
Deterministic parameter search, financial grammar trees, and multi-factor synthesis.
"""

import random
from typing import Dict, Any, List

class AlgorithmicEngine:
    """Pure algorithmic, deterministic quantitative alpha generator."""

    BASE_PATTERNS = [
        # 1. Capital Efficiency & 2-day VWAP Mean Reversion (Proven Sharpe 2.44+ archetype)
        {
            "template_name": "Capital Efficiency Tail Concentration",
            "code_template": (
                "oi_mom = rank(ts_delta(ts_backfill(operating_income, {fund_lb}), {fund_lb}) / cap);\n"
                "own_hist = rank(ts_rank(ts_backfill(ebitda, {fund_lb}) / (ts_backfill(enterprise_value, {fund_lb}) + 1), 250));\n"
                "eps_mom = rank(ts_delta(ts_backfill(anl4_afv4_eps_mean, 60), 60));\n"
                "cf_yield = rank(ts_backfill(cashflow_op, {fund_lb}) / cap);\n"
                "asset_turn = rank(ts_backfill(sales, {fund_lb}) / (ts_backfill(assets, {fund_lb}) + 1));\n"
                "fund = power(rank(0.25 * oi_mom + 0.15 * own_hist + 0.20 * eps_mom + 0.15 * cf_yield + 0.25 * asset_turn), {power_val});\n"
                "rev = power(0.70 * rank(-(close - ts_mean(vwap, {vwap_d})) / ts_mean(vwap, {vwap_d})) + 0.30 * rank(-returns), {power_val});\n"
                "group_neutralize(fund * rev, subindustry)"
            ),
            "delay": 1,
            "universe": "TOP3000",
            "decay": 22,
            "neutralization": "SUBINDUSTRY"
        },
        # 2. Operating Cash Flow & EBITDA Yield (Sharpe 2.22 archetype)
        {
            "template_name": "Operating Cashflow Yield Momentum",
            "code_template": (
                "oi_mom = rank(ts_delta(ts_backfill(operating_income, {fund_lb}), {fund_lb}) / cap);\n"
                "own_hist = rank(ts_rank(ts_backfill(ebitda, {fund_lb}) / (ts_backfill(enterprise_value, {fund_lb}) + 1), 250));\n"
                "eps_mom = rank(ts_delta(ts_backfill(anl4_afv4_eps_mean, 60), 60));\n"
                "cf_yield = rank(ts_backfill(cashflow_op, {fund_lb}) / cap);\n"
                "fund = power(rank(0.35 * oi_mom + 0.15 * own_hist + 0.35 * eps_mom + 0.15 * cf_yield), {power_val});\n"
                "rev = power(0.70 * rank(-(close - ts_mean(vwap, {vwap_d})) / ts_mean(vwap, {vwap_d})) + 0.30 * rank(-returns), {power_val});\n"
                "group_neutralize(fund * rev, subindustry)"
            ),
            "delay": 1,
            "universe": "TOP1000",
            "decay": 20,
            "neutralization": "SUBINDUSTRY"
        },
        # 3. Delay 0 Earnings Announcement PEAD with position holding
        {
            "template_name": "Delay 0 Earnings PEAD Held Reversal",
            "code_template": (
                "earn_tone = vec_avg(nws18_bee);\n"
                "event = abs(earn_tone) > 0;\n"
                "held_tone = trade_when(event, earn_tone, -1);\n"
                "intra_rev = rank(-(close - open) / open);\n"
                "group_neutralize(0.70 * held_tone + 0.30 * intra_rev, subindustry)"
            ),
            "delay": 0,
            "universe": "TOP3000",
            "decay": 12,
            "neutralization": "SUBINDUSTRY"
        },
        # 4. Delay 0 Share Repurchase Flow
        {
            "template_name": "Delay 0 Share Repurchase & Cash Yield",
            "code_template": (
                "event = ts_backfill(fn_payments_for_repurchase_of_common_stock_q, 60) > 0;\n"
                "buyback_yield = rank(ts_backfill(fn_payments_for_repurchase_of_common_stock_q, 60) / cap);\n"
                "cf_yield = rank(ts_backfill(cashflow_op, 120) / cap);\n"
                "fund = power(rank(0.50 * buyback_yield + 0.50 * cf_yield), 2.2);\n"
                "intra_rev = power(0.70 * rank(-(close - open) / open) + 0.30 * rank(-returns), 2.2);\n"
                "signal = group_neutralize(fund * intra_rev, subindustry);\n"
                "trade_when(event, signal, -1)"
            ),
            "delay": 0,
            "universe": "TOP3000",
            "decay": 15,
            "neutralization": "SUBINDUSTRY"
        },
        # 5. Alternative Data Network & Sentiment Orthogonal Factor
        {
            "template_name": "Alternative Data PageRank & Sentiment Synergy",
            "code_template": (
                "network = rank(pv13_com_page_rank);\n"
                "social_panic = rank(-ts_mean(snt_social_value, 5));\n"
                "news_tone = rank(ts_mean(mean_earnings_evaluation_sentiment, 5));\n"
                "eps_rev = rank(ts_delta(ts_backfill(anl4_afv4_eps_mean, 60), 60));\n"
                "alt_engine = power(rank(0.30 * eps_rev + 0.30 * network + 0.20 * social_panic + 0.20 * news_tone), {power_val});\n"
                "rev = power(0.70 * rank(-(close - ts_mean(vwap, {vwap_d})) / ts_mean(vwap, {vwap_d})) + 0.30 * rank(-returns), {power_val});\n"
                "group_neutralize(alt_engine * rev, subindustry)"
            ),
            "delay": 1,
            "universe": "TOP3000",
            "decay": 22,
            "neutralization": "SUBINDUSTRY"
        }
    ]

    @classmethod
    def generate_candidate(cls, pattern_idx: int = None) -> Dict[str, Any]:
        """Generates a mutated, optimized candidate ready for WorldQuant simulation."""
        if pattern_idx is None or pattern_idx < 0 or pattern_idx >= len(cls.BASE_PATTERNS):
            pattern = random.choice(cls.BASE_PATTERNS)
        else:
            pattern = cls.BASE_PATTERNS[pattern_idx]

        fund_lb = random.choice([90, 120, 150])
        power_val = random.choice([2.2, 2.5, 2.8])
        vwap_d = random.choice([2, 3])

        code = pattern["code_template"].format(
            fund_lb=fund_lb,
            power_val=power_val,
            vwap_d=vwap_d
        )

        name = f"AlgoBatch_{pattern['template_name'][:18]}_{random.randint(100, 999)}"

        return {
            "name": name,
            "expr": code,
            "region": "USA",
            "universe": pattern["universe"],
            "delay": pattern["delay"],
            "decay": pattern["decay"],
            "neutralization": pattern["neutralization"],
            "engine": "algorithmic"
        }
