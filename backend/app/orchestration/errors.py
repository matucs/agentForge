"""Errors that abort an orchestration run with a specific, real terminal
status — distinct from a generic node failure (`Run.status = "failed"`)."""


class BudgetExceededError(RuntimeError):
    """Raised when a run's accumulated estimated cost exceeds
    settings.max_run_budget_usd (spec §34). `service.py` catches this and
    sets Run.status = "stopped_by_budget"."""


def check_budget_exceeded(estimated_cost_usd: float, max_run_budget_usd: float) -> bool:
    return estimated_cost_usd > max_run_budget_usd
