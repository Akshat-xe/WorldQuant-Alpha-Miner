"""
Algorithmic Alpha Engine (No AI)
Deterministic parameter search, quantitative factor grammar, and closed-loop mutational adaptation.
"""

import re
import random
from typing import Dict, Any, List, Optional

class AlgorithmicEngine:
    """Pure algorithmic, deterministic quantitative alpha generator with closed-loop feedback."""

    BASE_PATTERNS = [
        # 1. Dual-Horizon Trend & Mean Reversion
        {
            "template_name": "Dual-Horizon Trend & Reversion",
            "code_template": (
                "fast_trend = rank(ts_mean(close, {fast_w}) - ts_mean(close, {slow_w}));\n"
                "reversal = rank(-returns);\n"
                "group_neutralize(0.60 * fast_trend + 0.40 * reversal, {neut})"
            ),
            "delay": 1,
            "universe": "TOP3000",
            "decay": 14,
            "neutralization": "SUBINDUSTRY"
        },
        # 2. Volume Flow Imbalance & Intraday Pressure
        {
            "template_name": "Volume Flow Imbalance",
            "code_template": (
                "flow = rank(volume / (adv20 + 1));\n"
                "pressure = rank(-(close - open) / (high - low + 0.001));\n"
                "group_neutralize(0.50 * flow + 0.50 * pressure, {neut})"
            ),
            "delay": 1,
            "universe": "TOP1000",
            "decay": 12,
            "neutralization": "SUBINDUSTRY"
        },
        # 3. High-Low Range Multi-Scale Mean Reversion
        {
            "template_name": "Range Position Mean Reversion",
            "code_template": (
                "range_pos = (close - ts_min(low, {lookback})) / (ts_max(high, {lookback}) - ts_min(low, {lookback}) + 0.001);\n"
                "reversal = power(rank(-range_pos), {power_val});\n"
                "group_neutralize(reversal, {neut})"
            ),
            "delay": 1,
            "universe": "TOP3000",
            "decay": 16,
            "neutralization": "SUBINDUSTRY"
        },
        # 4. Multi-Scale Volatility Compression & Breakout
        {
            "template_name": "Volatility Compression Breakout",
            "code_template": (
                "vol_ratio = ts_std_dev(returns, 10) / (ts_std_dev(returns, 60) + 0.001);\n"
                "momentum = rank(ts_delta(close, 5));\n"
                "group_neutralize(rank(-vol_ratio) * momentum, {neut})"
            ),
            "delay": 1,
            "universe": "TOP3000",
            "decay": 15,
            "neutralization": "SUBINDUSTRY"
        },
        # 5. Operating Cash Flow Yield & VWAP Reversion
        {
            "template_name": "Cash Flow Yield & VWAP Reversion",
            "code_template": (
                "cf_yield = rank(ts_backfill(cashflow_op, {fund_lb}) / cap);\n"
                "rev = rank(-(close - ts_mean(vwap, {vwap_d})) / (ts_mean(vwap, {vwap_d}) + 0.001));\n"
                "group_neutralize(0.55 * cf_yield + 0.45 * rev, {neut})"
            ),
            "delay": 1,
            "universe": "TOP1000",
            "decay": 18,
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

        fast_w = random.choice([3, 5, 8])
        slow_w = random.choice([15, 20, 30])
        lookback = random.choice([5, 10, 15, 20])
        power_val = random.choice([1.8, 2.2, 2.5])
        fund_lb = random.choice([90, 120, 180])
        vwap_d = random.choice([2, 3, 5])
        neut = pattern.get("neutralization", "subindustry").lower()

        code = pattern["code_template"].format(
            fast_w=fast_w,
            slow_w=slow_w,
            lookback=lookback,
            power_val=power_val,
            fund_lb=fund_lb,
            vwap_d=vwap_d,
            neut=neut
        )

        name = f"Algo_{pattern['template_name'][:18].replace(' ', '')}_{random.randint(100, 999)}"

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

    @classmethod
    def mutate_and_improve(cls, candidate: Dict[str, Any], evaluation: Dict[str, Any]) -> Dict[str, Any]:
        """
        Consumes previous backtest evaluation and applies closed-loop mutational heuristics.
        Returns a new candidate dict and an explanation of the mutation applied.
        """
        mutated = dict(candidate)
        expr = mutated.get("expr", "")
        decay = int(mutated.get("decay", 12))
        universe = mutated.get("universe", "TOP3000")
        neut = mutated.get("neutralization", "SUBINDUSTRY")

        metrics = evaluation.get("metrics", {})
        hurdle_failures = evaluation.get("hurdle_failures", [])
        turnover = metrics.get("turnover", 0.0)
        sharpe = metrics.get("sharpe", 0.0)
        self_corr = metrics.get("self_corr", 0.0)

        applied_actions = []

        # 1. Turnover Failure or High Turnover (> 70%)
        has_turnover_fail = any("TURNOVER" in f.upper() for f in hurdle_failures) or (turnover > 0.70)
        if has_turnover_fail:
            new_decay = min(40, decay + random.choice([6, 8, 10]))
            mutated["decay"] = new_decay
            applied_actions.append(f"Raised decay from {decay} to {new_decay}")

            # Apply smoothing to raw return if present
            if "-returns" in expr and "ts_mean(-returns" not in expr:
                expr = expr.replace("-returns", "ts_mean(-returns, 3)")
                applied_actions.append("Smoothed entry signal with ts_mean(..., 3)")
            elif "ts_delta(close" in expr:
                expr = re.sub(r"ts_delta\(close,\s*\d+\)", "ts_delta(ts_mean(close, 3), 5)", expr)
                applied_actions.append("Smoothed price delta with ts_mean window")

        # 2. Self-Correlation Failure (>= 0.70)
        has_corr_fail = any("CORRELATION" in f.upper() for f in hurdle_failures) or (self_corr >= 0.70)
        if has_corr_fail:
            # Shift neutralization
            if neut.upper() == "SUBINDUSTRY":
                mutated["neutralization"] = "SECTOR"
                expr = re.sub(r"group_neutralize\((.+),\s*subindustry\)", r"group_neutralize(\1, sector)", expr, flags=re.IGNORECASE)
                applied_actions.append("Shifted neutralization: SUBINDUSTRY -> SECTOR")
            elif neut.upper() == "NONE":
                mutated["neutralization"] = "SUBINDUSTRY"
                if "group_neutralize" not in expr:
                    expr = f"group_neutralize({expr.strip()}, subindustry)"
                applied_actions.append("Injected SUBINDUSTRY group neutralization")
            
            # Switch universe if stuck
            if universe == "TOP3000":
                mutated["universe"] = "TOP2000"
                applied_actions.append("Rotated universe: TOP3000 -> TOP2000")

        # 3. Low Sharpe (< 1.25)
        has_sharpe_fail = any("SHARPE" in f.upper() for f in hurdle_failures) or (sharpe < 1.25)
        if has_sharpe_fail and not has_turnover_fail:
            # Inject power transformation to concentrate tail weights
            if "power(" not in expr:
                # Wrap signal before group_neutralize or wrap final expression
                if "group_neutralize(" in expr:
                    expr = re.sub(r"group_neutralize\((.+),\s*([a-zA-Z0-9_]+)\)", r"group_neutralize(power(\1, 2.2), \2)", expr, flags=re.DOTALL)
                else:
                    expr = f"power({expr.strip()}, 2.2)"
                applied_actions.append("Applied non-linear power(..., 2.2) conviction weighting")
            else:
                # Bump power from 1.8 -> 2.4 or 2.2 -> 2.6
                expr = re.sub(r"power\((.+),\s*([0-9\.]+)\)", r"power(\1, 2.5)", expr, flags=re.DOTALL)
                applied_actions.append("Adjusted conviction power exponent to 2.5")

        if not applied_actions:
            # Fine-tune decay slightly
            new_decay = min(35, decay + 4)
            mutated["decay"] = new_decay
            applied_actions.append(f"Tuned holding decay: {decay} -> {new_decay}")

        mutated["expr"] = expr
        mutated["name"] = f"{candidate.get('name', 'Alpha')}_v{random.randint(2, 99)}"

        return {
            "candidate": mutated,
            "actions_summary": "; ".join(applied_actions)
        }
