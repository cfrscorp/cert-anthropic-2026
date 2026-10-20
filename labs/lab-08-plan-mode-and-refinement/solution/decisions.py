"""Reference implementation: workflow-mode and refinement decision helpers.

This module encodes the judgment calls from CCAR-F Task Statements 3.4 and 3.5 as
three small, pure functions so they can be exercised deterministically:

    choose_mode(task)          -> "plan" | "direct"
    refinement_strategy(issues)-> "single_message" | "sequential"
    should_use_explore(task)   -> bool

The point of the lab is the *reasoning*, not the plumbing. Each function reduces
a task/issue description (a plain dict) to the choice the exam guide prescribes:

- Plan mode is for complex work: large-scale/multi-file changes, architectural
  decisions, or problems with multiple valid approaches — anywhere exploration
  and design should happen *before* committing to changes to avoid costly rework.
- Direct execution is for simple, well-scoped changes (e.g. a single-file bug fix
  with a clear stack trace, or adding one validation conditional).
- The Explore subagent isolates verbose, multi-phase discovery so its output does
  not exhaust the main conversation's context window.
- When fixing multiple issues, send them in ONE message if the fixes interact
  (a change to one affects another); iterate SEQUENTIALLY when they are
  independent (fixing one cannot change the others).

All functions are pure and side-effect free, so the tests can parametrize over
the canonical cases in ``scenarios.md`` and assert exact labels.
"""

from __future__ import annotations

from typing import Any

__all__ = ["choose_mode", "refinement_strategy", "should_use_explore"]


def choose_mode(task: dict[str, Any]) -> str:
    """Return ``"plan"`` or ``"direct"`` for a task (Task Statement 3.4).

    A task is a dict describing the change. Recognized features:

        multi_file_count (int):          how many files the change touches.
        architectural (bool):            does it involve architectural decisions
                                         (service boundaries, module dependencies)?
        multiple_valid_approaches (bool):are there several viable designs to
                                         choose between (e.g. two integration
                                         approaches with different infra)?
        clear_scope (bool):              is the change well understood and bounded
                                         up front? Defaults to True.

    Decision rule — choose **plan** if ANY plan trigger is present:
        * ``architectural`` is True, or
        * ``multiple_valid_approaches`` is True, or
        * the change is multi-file (``multi_file_count > 1``), or
        * the scope is not clear (``clear_scope`` is False).
    Otherwise the change is simple and well-scoped → **direct**.

    Rationale (Sample Question 5): a monolith→microservices restructuring is
    architectural, multi-file, and multi-approach, so its complexity is *already
    stated* — you enter plan mode up front rather than "switching later" or
    guessing a structure with upfront instructions. A single-file bug fix with a
    clear stack trace has none of these triggers → direct execution.
    """
    architectural = bool(task.get("architectural", False))
    multiple_valid_approaches = bool(task.get("multiple_valid_approaches", False))
    multi_file_count = int(task.get("multi_file_count", 1))
    clear_scope = bool(task.get("clear_scope", True))

    multi_file = multi_file_count > 1

    if architectural or multiple_valid_approaches or multi_file or not clear_scope:
        return "plan"
    return "direct"


def refinement_strategy(issues: list[dict[str, Any]]) -> str:
    """Return ``"single_message"`` or ``"sequential"`` (Task Statement 3.5).

    ``issues`` is a list of dicts, each describing a problem to fix. Recognized
    feature per issue:

        interacts_with_others (bool): does fixing this issue change, or depend on,
                                      the fix for another issue in the set?

    Decision rule:
        * If ANY issue interacts with the others, address them all in a **single
          detailed message** so the model can reconcile the coupled fixes at once.
        * If every issue is independent, iterate **sequentially** — fix one, verify,
          then move to the next — so each change is easy to review in isolation.

    An empty list has nothing coupled, so it degenerates to ``"sequential"``.
    """
    if any(bool(issue.get("interacts_with_others", False)) for issue in issues):
        return "single_message"
    return "sequential"


def should_use_explore(task: dict[str, Any]) -> bool:
    """Return True if the task warrants delegating discovery to the Explore subagent.

    Recognized features:

        verbose_discovery (bool):        does the task require a noisy discovery
                                         phase (reading many files, tracing flows)
                                         whose raw output has little lasting value?
        multi_phase (bool):              is discovery one of several phases, so
                                         its output would crowd out later work?
        context_exhaustion_risk (bool): would keeping that output inline risk
                                         exhausting the main context window?

    Decision rule: use Explore only when there is verbose discovery AND it would
    otherwise burden the main conversation — i.e. it is part of a multi-phase task
    or carries a context-exhaustion risk. A quick, self-contained lookup does not
    need a subagent; the overhead is not worth it.
    """
    verbose_discovery = bool(task.get("verbose_discovery", False))
    multi_phase = bool(task.get("multi_phase", False))
    context_exhaustion_risk = bool(task.get("context_exhaustion_risk", False))

    return verbose_discovery and (multi_phase or context_exhaustion_risk)
