import sys
from typing import List, Dict, Any
from .evaluator import EvaluationResult

class PipelineReporter:
    """
    Formats and prints human-readable terminal scorecards, summary tables,
    and audit metrics for evaluated alphas.
    """

    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"
    RESET = "\033[0m"

    @classmethod
    def print_banner(cls, text: str) -> None:
        print("\n" + "=" * 80)
        print(f"{cls.BOLD}{cls.CYAN}{text.center(80)}{cls.RESET}")
        print("=" * 80)

    @classmethod
    def print_alpha_card(cls, res: EvaluationResult) -> None:
        print("\n" + "-" * 80)
        status_tag = f"{cls.GREEN}{cls.BOLD}★ SUBMITTABLE (KEPT UNSUBMITTED) ★{cls.RESET}" if res.is_submittable else f"{cls.RED}✗ INELIGIBLE FOR SUBMISSION{cls.RESET}"
        
        print(f"Alpha ID       : {cls.BOLD}{res.id}{cls.RESET} ({res.name})")
        print(f"Expression     : {cls.CYAN}{res.expression}{cls.RESET}")
        print(f"Settings       : {res.region} | {res.universe} | Delay {res.delay} | Decay {res.decay} | Neut: {res.neutralization}")
        to_str = f"{res.turnover:.4f}" if res.turnover is not None else "N/A"
        print(f"Metrics        : Sharpe: {res.sharpe} | Fitness: {res.fitness} | Turnover: {to_str} | Returns: {res.returns}")
        print(f"Risk           : Max Drawdown: {res.drawdown} | Margin: {res.margin}")
        
        corr_str = f"{res.max_self_correlation:.4f}" if res.max_self_correlation is not None else "None detected"
        print(f"Self-Corr Max  : {corr_str}")
        print(f"Verdict        : {status_tag}")
        
        if res.fail_reasons:
            print(f"{cls.YELLOW}Failed Hurdle(s):{cls.RESET}")
            for r in res.fail_reasons:
                print(f"   - {r}")
        print("-" * 80)

    @classmethod
    def print_batch_summary(cls, results: List[EvaluationResult]) -> None:
        cls.print_banner("BATCH EVALUATION SCORECARD SUMMARY")
        if not results:
            print("No alphas evaluated in this batch.")
            return

        header = f"{'ID':<10} | {'SHARPE':<7} | {'FITNESS':<7} | {'TURNOVER':<9} | {'SELF-CORR':<10} | {'VERDICT':<32}"
        print(header)
        print("-" * len(header))

        submittable_count = 0
        for r in results:
            sh_str = f"{r.sharpe:.2f}" if r.sharpe is not None else "N/A"
            fit_str = f"{r.fitness:.2f}" if r.fitness is not None else "N/A"
            to_str = f"{r.turnover*100:.1f}%" if r.turnover is not None else "N/A"
            sc_str = f"{r.max_self_correlation:.2f}" if r.max_self_correlation is not None else "--"

            if r.is_submittable:
                submittable_count += 1
                verdict = f"{cls.GREEN}★ SUBMITTABLE (UNSUBMITTED){cls.RESET}"
            else:
                verdict = f"{cls.RED}FAIL ({len(r.fail_reasons)} hurdles){cls.RESET}"

            print(f"{r.id:<10} | {sh_str:<7} | {fit_str:<7} | {to_str:<9} | {sc_str:<10} | {verdict:<32}")

        print("-" * len(header))
        print(f"Total Evaluated : {len(results)}")
        print(f"Submittable Alphas: {cls.GREEN}{cls.BOLD}{submittable_count}{cls.RESET} (Kept unsubmitted as requested)")
        print(f"Ineligible Alphas : {len(results) - submittable_count}")
        print("=" * 80)
