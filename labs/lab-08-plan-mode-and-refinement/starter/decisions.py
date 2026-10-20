"""Starter scaffold: workflow-mode and refinement decision helpers.

Implement three pure functions that encode the judgment calls from CCAR-F Task
Statements 3.4 (plan vs direct execution, and the Explore subagent) and 3.5
(iterative refinement). Each takes a plain dict / list of dicts describing the
work and returns the choice the exam guide prescribes.

Read ``../README.md`` for the full background and ``../scenarios.md`` for the
canonical cases the tests use. The reference decision rules are summarized inline
below — fill in each function so it satisfies them, then delete the
``NotImplementedError`` lines.

Keep every function PURE (no I/O, no globals): the tests parametrize over the
canonical scenarios and assert exact return labels.

Run the tests from the ``labs/`` directory:  uv run pytest lab-08-plan-mode-and-refinement
"""

from __future__ import annotations

from typing import Any

__all__ = ["choose_mode", "refinement_strategy", "should_use_explore"]


def choose_mode(task: dict[str, Any]) -> str:
    """Return ``"plan"`` or ``"direct"`` for a task (Task Statement 3.4).

    ``task`` features you should read (with sensible defaults):
        multi_file_count (int, default 1)
        architectural (bool, default False)
        multiple_valid_approaches (bool, default False)
        clear_scope (bool, default True)

    Return ``"plan"`` if ANY plan trigger is present:
        * architectural is True, OR
        * multiple_valid_approaches is True, OR
        * the change is multi-file (multi_file_count > 1), OR
        * the scope is not clear (clear_scope is False).
    Otherwise the change is simple and well-scoped → return ``"direct"``.
    """
    # TODO: read the four features from `task` with the defaults above.
    # TODO: return "plan" if any plan trigger is present, else "direct".
    raise NotImplementedError("Implement choose_mode (see README.md and scenarios.md).")


def refinement_strategy(issues: list[dict[str, Any]]) -> str:
    """Return ``"single_message"`` or ``"sequential"`` (Task Statement 3.5).

    Each issue dict may carry ``interacts_with_others`` (bool, default False).

    Return ``"single_message"`` if ANY issue interacts with the others (send the
    coupled fixes together so the model reconciles them at once). Otherwise every
    issue is independent → return ``"sequential"`` (fix one at a time). An empty
    list has nothing coupled → ``"sequential"``.
    """
    # TODO: if any issue has interacts_with_others truthy -> "single_message".
    # TODO: else -> "sequential".
    raise NotImplementedError("Implement refinement_strategy (see README.md and scenarios.md).")


def should_use_explore(task: dict[str, Any]) -> bool:
    """Return True if discovery should be delegated to the Explore subagent.

    ``task`` features (all bool, default False):
        verbose_discovery, multi_phase, context_exhaustion_risk

    Return True only when there is verbose discovery AND it would burden the main
    conversation — i.e. verbose_discovery is True AND (multi_phase OR
    context_exhaustion_risk). A quick, self-contained lookup → False.
    """
    # TODO: return verbose_discovery and (multi_phase or context_exhaustion_risk).
    raise NotImplementedError("Implement should_use_explore (see README.md and scenarios.md).")
