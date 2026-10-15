import time
import logging
import threading
from typing import Dict, Any, Optional, Callable

from .database import AlphaDatabase
from .client import BrainClient

logger = logging.getLogger(__name__)

class BackgroundCorrelationWorker:
    """
    Background worker that audits the WorldQuant BRAIN self-correlation matrix
    for unsubmitted alphas when no higher-priority simulation tasks are running.

    Removes any failing alphas from submittable status, and persists verified
    correlation scores locally in SQLite so completed checks are never re-queried.
    """
    def __init__(
        self,
        db_path: str,
        is_idle_func: Optional[Callable[[], bool]] = None,
        poll_interval_sec: float = 1.0
    ):
        self.db_path = db_path
        self.is_idle_func = is_idle_func or (lambda: True)
        self.poll_interval_sec = poll_interval_sec

        self.thread: Optional[threading.Thread] = None
        self.stop_event = threading.Event()
        self.lock = threading.Lock()

        self.client: Optional[BrainClient] = None
        self.is_running = False
        self.is_paused = False
        self.current_alpha_id: Optional[str] = None

    def start(self, client: BrainClient) -> None:
        """Starts or resumes the background correlation worker with an authenticated client."""
        with self.lock:
            self.client = client
            if self.is_running and self.thread and self.thread.is_alive():
                return

            self.stop_event.clear()
            self.is_running = True
            self.thread = threading.Thread(target=self._worker_loop, daemon=True, name="CorrelationWorker")
            self.thread.start()
            logger.info("[*] Background correlation worker started.")

    def stop(self) -> None:
        """Signals the background worker thread to stop."""
        with self.lock:
            self.stop_event.set()
            self.is_running = False
            self.current_alpha_id = None
            logger.info("[*] Background correlation worker stopping.")

    def _worker_loop(self) -> None:
        db = AlphaDatabase(self.db_path)

        while not self.stop_event.is_set():
            # 1. Check if higher-priority tasks (simulations/audits) are currently active
            if not self.is_idle_func():
                self.is_paused = True
                self.current_alpha_id = None
                time.sleep(1.5)
                continue

            self.is_paused = False

            # 2. Fetch the next unsubmitted alpha needing correlation check
            unchecked = db.get_unchecked_unsubmitted_alphas(limit=1)
            if not unchecked:
                self.current_alpha_id = None
                # All caught up; sleep for a short duration before checking again
                time.sleep(3.0)
                continue

            target = unchecked[0]
            alpha_id = target["id"]
            self.current_alpha_id = alpha_id

            # Ensure client is still available
            if not self.client:
                time.sleep(2.0)
                continue

            try:
                # 3. Query WorldQuant BRAIN platform checks for this alpha
                chk = self.client.run_platform_checks(alpha_id)
                if not chk or "is" not in chk:
                    # Platform busy or timed out; sleep briefly and re-attempt
                    time.sleep(self.poll_interval_sec)
                    continue

                is_data = chk.get("is") or {}
                checks = is_data.get("checks") or []
                self_corr = is_data.get("selfCorrelated") or {}
                max_corr = self_corr.get("max")

                self_chk = next((c for c in checks if isinstance(c, dict) and c.get("name") == "SELF_CORRELATION"), None)
                chk_result = (self_chk.get("result") or "").upper() if self_chk else ""

                is_fail = (chk_result in ("FAIL", "ERROR")) or (max_corr is not None and max_corr >= 0.70)
                is_pending = (chk_result == "PENDING")

                if is_fail:
                    corr_val = max_corr if max_corr is not None else (self_chk.get("value") if self_chk else None)
                    reason = f"SELF_CORRELATION failed ({corr_val:.4f} >= 0.70)" if corr_val is not None else "SELF_CORRELATION hurdle failed"
                    db.update_correlation_result(
                        alpha_id=alpha_id,
                        max_correlation=corr_val,
                        passed=False,
                        fail_reason=reason,
                        checks=checks
                    )
                    logger.info(f"[!] Correlation check FAILED for {alpha_id} ({reason}). Removed from submittable.")

                elif is_pending:
                    # If alpha already failed initial hurdles (e.g. LOW_SHARPE), BRAIN omits self-correlation
                    if target.get("is_submittable") == 0:
                        db.update_correlation_result(
                            alpha_id=alpha_id,
                            max_correlation=None,
                            passed=False,
                            fail_reason="SELF_CORRELATION skipped by platform (hurdles failed)",
                            checks=checks
                        )
                    else:
                        # Genuine pending on BRAIN for submittable alpha; let BRAIN finish computing
                        time.sleep(2.0)
                        continue
                else:
                    # Successfully passed platform correlation check!
                    db.update_correlation_result(
                        alpha_id=alpha_id,
                        max_correlation=max_corr,
                        passed=True,
                        checks=checks
                    )
                    logger.info(f"[✓] Correlation check PASSED for {alpha_id} (max: {max_corr}).")

            except Exception as e:
                logger.warning(f"[!] Background correlation check error for {alpha_id}: {e}")
                time.sleep(2.0)
            finally:
                self.current_alpha_id = None
                # Rate limit pacing
                time.sleep(self.poll_interval_sec)

        self.is_running = False
        self.is_paused = False
        self.current_alpha_id = None

    def get_status(self) -> Dict[str, Any]:
        """Returns live execution state and SQLite completion progress."""
        db = AlphaDatabase(self.db_path)
        progress = db.get_correlation_progress()
        total = progress["total_unsubmitted"]
        checked = progress["checked_count"]
        progress_pct = round((checked / total * 100), 1) if total > 0 else 100.0

        return {
            "is_running": self.is_running,
            "is_paused": self.is_paused,
            "current_alpha_id": self.current_alpha_id,
            "total_unsubmitted": total,
            "checked_count": checked,
            "remaining_count": progress["remaining_count"],
            "passed_count": progress["passed_count"],
            "failed_count": progress["failed_count"],
            "progress_pct": progress_pct,
            "complete": progress["complete"]
        }
