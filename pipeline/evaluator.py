from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
import logging

from .config import PipelineConfig
from .client import BrainClient

logger = logging.getLogger(__name__)

@dataclass
class EvaluationResult:
    id: str
    name: str
    expression: str
    region: str
    universe: str
    delay: int
    decay: int
    neutralization: str
    sharpe: Optional[float] = None
    fitness: Optional[float] = None
    turnover: Optional[float] = None
    returns: Optional[float] = None
    drawdown: Optional[float] = None
    margin: Optional[float] = None
    is_submittable: bool = False
    checks: List[Dict[str, Any]] = field(default_factory=list)
    fail_reasons: List[str] = field(default_factory=list)
    max_self_correlation: Optional[float] = None
    status: str = "UNSUBMITTED"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "expression": self.expression,
            "region": self.region,
            "universe": self.universe,
            "delay": self.delay,
            "decay": self.decay,
            "neutralization": self.neutralization,
            "sharpe": self.sharpe,
            "fitness": self.fitness,
            "turnover": self.turnover,
            "returns": self.returns,
            "drawdown": self.drawdown,
            "margin": self.margin,
            "is_submittable": self.is_submittable,
            "checks": self.checks,
            "fail_reasons": self.fail_reasons,
            "max_self_correlation": self.max_self_correlation,
            "status": self.status
        }

class AlphaEvaluator:
    """
    Evaluates alpha candidates against WorldQuant BRAIN performance hurdles
    and platform validation checks.
    """
    def __init__(
        self,
        client: BrainClient,
        config: Optional[PipelineConfig] = None,
        db: Optional[Any] = None
    ):
        self.client = client
        self.config = config or PipelineConfig()
        self.db = db

    def evaluate_alpha(
        self,
        alpha_data: Any,
        name: Optional[str] = None
    ) -> EvaluationResult:
        if isinstance(alpha_data, str):
            alpha_id = alpha_data
            fetched = self.client.fetch_alpha(alpha_id)
            if not fetched:
                return EvaluationResult(
                    id=alpha_id,
                    name=name or alpha_id,
                    expression="",
                    region=self.config.default_region,
                    universe=self.config.default_universe,
                    delay=self.config.default_delay,
                    decay=self.config.default_decay,
                    neutralization=self.config.default_neutralization,
                    fail_reasons=[f"Unable to fetch alpha record for ID '{alpha_id}'"]
                )
            alpha_data = fetched

        alpha_id = alpha_data.get("id", "")
        regular = alpha_data.get("regular", {})
        expr = regular.get("code") if isinstance(regular, dict) else str(regular)
        settings = alpha_data.get("settings", {})
        metrics = alpha_data.get("is", {})
        
        alpha_name = name or alpha_data.get("name") or expr or alpha_id
        
        sharpe = metrics.get("sharpe")
        fitness = metrics.get("fitness")
        turnover = metrics.get("turnover")
        returns = metrics.get("returns")
        drawdown = metrics.get("drawdown")
        margin = metrics.get("margin")

        fail_reasons: List[str] = []

        # 1. Evaluate baseline metric hurdles
        if sharpe is None or sharpe < self.config.min_sharpe:
            fail_reasons.append(f"Sharpe {sharpe} < min required {self.config.min_sharpe}")
            
        if fitness is None or fitness < self.config.min_fitness:
            fail_reasons.append(f"Fitness {fitness} < min required {self.config.min_fitness}")
            
        if turnover is None:
            fail_reasons.append("Turnover metric is missing")
        elif turnover < self.config.min_turnover:
            fail_reasons.append(f"Turnover {turnover:.4f} < min {self.config.min_turnover}")
        elif turnover > self.config.max_turnover:
            fail_reasons.append(f"Turnover {turnover:.4f} > max {self.config.max_turnover}")

        # 2. Run / fetch full platform checks from /alphas/{id}/check
        checks_data = self.client.run_platform_checks(alpha_id)
        max_self_corr = None
        checks_list = []

        if checks_data and "is" in checks_data:
            checks_list = checks_data.get("is", {}).get("checks", [])
            self_corr_info = checks_data.get("is", {}).get("selfCorrelated", {})
            if isinstance(self_corr_info, dict):
                max_self_corr = self_corr_info.get("max")
        else:
            # Fallback to existing checks inside alpha_data
            checks_list = metrics.get("checks", [])

        # 3. Analyze checks for any FAIL or pending items
        for check in checks_list:
            c_name = check.get("name")
            c_res = check.get("result")
            c_val = check.get("value")
            c_lim = check.get("limit")

            if c_res == "FAIL":
                fail_reasons.append(f"Platform Check FAIL: {c_name} (val: {c_val}, limit: {c_lim})")
            elif c_res == "PENDING" and c_name == "SELF_CORRELATION":
                fail_reasons.append("Self-correlation check pending / unconfirmed")

        if max_self_corr is not None and max_self_corr > self.config.max_self_correlation:
            fail_reasons.append(f"Self-correlation {max_self_corr:.4f} > limit {self.config.max_self_correlation}")

        is_submittable = len(fail_reasons) == 0

        res = EvaluationResult(
            id=alpha_id,
            name=alpha_name,
            expression=expr,
            region=settings.get("region", self.config.default_region),
            universe=settings.get("universe", self.config.default_universe),
            delay=settings.get("delay", self.config.default_delay),
            decay=settings.get("decay", self.config.default_decay),
            neutralization=settings.get("neutralization", self.config.default_neutralization),
            sharpe=sharpe,
            fitness=fitness,
            turnover=turnover,
            returns=returns,
            drawdown=drawdown,
            margin=margin,
            is_submittable=is_submittable,
            checks=checks_list,
            fail_reasons=fail_reasons,
            max_self_correlation=max_self_corr,
            status=alpha_data.get("status", "UNSUBMITTED")
        )

        if self.db and hasattr(self.db, "save_evaluation"):
            try:
                self.db.save_evaluation(res.to_dict())
            except Exception as e:
                logger.warning(f"Could not auto-save evaluation to db: {e}")

        return res

