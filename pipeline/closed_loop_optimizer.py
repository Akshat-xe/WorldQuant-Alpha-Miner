"""
Closed-Loop Studio Optimizer
Autonomous multi-iteration feedback loop: Simulation 1 -> Simulation X.
Evaluates platform hurdles, diagnoses failures, mutates parameters/code,
and tracks step-by-step evolution until the alpha becomes submittable.
"""

import time
import uuid
import logging
import threading
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from .client import BrainClient
from .evaluator import AlphaEvaluator
from .engine_algorithmic import AlgorithmicEngine
from .config import PipelineConfig

logger = logging.getLogger(__name__)

class ClosedLoopStudioOptimizer:
    _lock = threading.Lock()
    _sessions: Dict[str, Dict[str, Any]] = {}

    @classmethod
    def get_session(cls, session_id: str) -> Optional[Dict[str, Any]]:
        with cls._lock:
            session = cls._sessions.get(session_id)
            if not session:
                return None
            return dict(session)

    @classmethod
    def stop_session(cls, session_id: str) -> bool:
        with cls._lock:
            session = cls._sessions.get(session_id)
            if session and session.get("status") == "RUNNING":
                session["status"] = "STOPPED"
                session["logs"].append(f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] [!] Evolution session stopped by user.")
                return True
            return False

    @classmethod
    def start_session(
        cls,
        initial_candidate: Dict[str, Any],
        client: BrainClient,
        db: Optional[Any] = None,
        config: Optional[PipelineConfig] = None,
        max_iterations: int = 5,
        target_sharpe: float = 1.25
    ) -> str:
        session_id = f"evo_{uuid.uuid4().hex[:8]}"
        cfg = config or PipelineConfig()

        session_data = {
            "session_id": session_id,
            "status": "RUNNING",  # RUNNING, SUBMITTABLE, MAX_ITERATIONS, STOPPED, ERROR
            "created_at": datetime.now(timezone.utc).isoformat(),
            "target_sharpe": target_sharpe,
            "max_iterations": max_iterations,
            "current_step": 0,
            "total_steps": 0,
            "is_submittable": False,
            "submittable_alpha_id": None,
            "logs": [f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] [*] Initialized Evolution Session {session_id}"],
            "steps": []
        }

        with cls._lock:
            cls._sessions[session_id] = session_data

        t = threading.Thread(
            target=cls._run_loop,
            args=(session_id, initial_candidate, client, db, cfg, max_iterations, target_sharpe),
            daemon=True
        )
        t.start()
        return session_id

    @classmethod
    def _run_loop(
        cls,
        session_id: str,
        initial_candidate: Dict[str, Any],
        client: BrainClient,
        db: Optional[Any],
        config: PipelineConfig,
        max_iterations: int,
        target_sharpe: float
    ):
        evaluator = AlphaEvaluator(client=client, config=config, db=db)
        candidate = dict(initial_candidate)

        for step_idx in range(1, max_iterations + 1):
            with cls._lock:
                session = cls._sessions.get(session_id)
                if not session or session["status"] == "STOPPED":
                    logger.info(f"Session {session_id} was stopped or deleted.")
                    return
                session["current_step"] = step_idx
                session["logs"].append(
                    f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] [Step {step_idx}/{max_iterations}] Dispatching simulation to WorldQuant BRAIN..."
                )

            # 1. Run simulation via BrainClient
            try:
                alpha_data = client.simulate_candidate(candidate)
            except Exception as e:
                logger.error(f"Error simulating candidate in session {session_id}: {e}")
                alpha_data = None

            if not alpha_data:
                with cls._lock:
                    session = cls._sessions.get(session_id)
                    if session:
                        session["status"] = "ERROR"
                        session["logs"].append(f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] [!] Simulation failed or timed out on BRAIN.")
                return

            alpha_id = alpha_data.get("id", "UNKNOWN")

            # 2. Evaluate candidate with AlphaEvaluator
            eval_res = evaluator.evaluate_alpha(alpha_data, name=candidate.get("name"))
            sharpe = eval_res.sharpe if eval_res.sharpe is not None else 0.0
            turnover = eval_res.turnover if eval_res.turnover is not None else 0.0
            fitness = eval_res.fitness if eval_res.fitness is not None else 0.0
            margin = eval_res.margin if eval_res.margin is not None else 0.0
            self_corr = eval_res.max_self_correlation if eval_res.max_self_correlation is not None else 0.0
            fail_reasons = eval_res.fail_reasons or []

            # Check if all hurdles passed
            is_submittable = eval_res.is_submittable and (sharpe >= target_sharpe)

            step_entry = {
                "step": step_idx,
                "alpha_id": alpha_id,
                "name": candidate.get("name", f"Alpha_Step_{step_idx}"),
                "expr": candidate.get("expr", ""),
                "decay": candidate.get("decay", 12),
                "neutralization": candidate.get("neutralization", "SUBINDUSTRY"),
                "universe": candidate.get("universe", "TOP3000"),
                "metrics": {
                    "sharpe": round(sharpe, 4),
                    "turnover": round(turnover, 4),
                    "fitness": round(fitness, 4),
                    "margin": round(margin, 5),
                    "self_corr": round(self_corr, 4)
                },
                "hurdles_passed": is_submittable,
                "hurdle_failures": fail_reasons,
                "mutation_applied": None,
                "feedback_rationale": ""
            }

            if is_submittable:
                step_entry["feedback_rationale"] = (
                    f"ALL 8 PLATFORM HURDLES PASSED! Sharpe {sharpe:.2f} >= {target_sharpe:.2f}, "
                    f"Turnover {turnover * 100:.1f}%, Self-Correlation {self_corr:.2f}. Alpha is submittable!"
                )
                with cls._lock:
                    session = cls._sessions.get(session_id)
                    if session:
                        session["steps"].append(step_entry)
                        session["total_steps"] = len(session["steps"])
                        session["is_submittable"] = True
                        session["submittable_alpha_id"] = alpha_id
                        session["status"] = "SUBMITTABLE"
                        session["logs"].append(
                            f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] [★] ALPHA SUBMITTABLE at Step {step_idx}! (Alpha ID: {alpha_id})"
                        )
                return

            # If not submittable and we reached max_iterations
            if step_idx >= max_iterations:
                step_entry["feedback_rationale"] = (
                    f"Reached maximum limit of {max_iterations} iterations without clearing all platform hurdles. "
                    f"Remaining issues: {'; '.join(fail_reasons[:2])}"
                )
                with cls._lock:
                    session = cls._sessions.get(session_id)
                    if session:
                        session["steps"].append(step_entry)
                        session["total_steps"] = len(session["steps"])
                        session["status"] = "MAX_ITERATIONS"
                        session["logs"].append(
                            f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] [!] Evolution completed: Max iterations ({max_iterations}) reached."
                        )
                return

            # Apply mutation heuristic for next iteration
            mutation_res = AlgorithmicEngine.mutate_and_improve(
                candidate=candidate,
                evaluation={
                    "metrics": {"sharpe": sharpe, "turnover": turnover, "fitness": fitness, "self_corr": self_corr},
                    "hurdle_failures": fail_reasons
                }
            )

            next_candidate = mutation_res["candidate"]
            applied_action = mutation_res["actions_summary"]

            step_entry["mutation_applied"] = applied_action
            step_entry["feedback_rationale"] = (
                f"Platform checks failed ({fail_reasons[0] if fail_reasons else 'Sub-optimal Sharpe'}). "
                f"Autonomous mutation triggered: {applied_action}"
            )

            with cls._lock:
                session = cls._sessions.get(session_id)
                if session:
                    session["steps"].append(step_entry)
                    session["total_steps"] = len(session["steps"])
                    session["logs"].append(
                        f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] [->] Step {step_idx} failed hurdles: {', '.join(fail_reasons[:2])}. "
                        f"Applying mutation: {applied_action}"
                    )

            candidate = next_candidate
            time.sleep(1.0)
