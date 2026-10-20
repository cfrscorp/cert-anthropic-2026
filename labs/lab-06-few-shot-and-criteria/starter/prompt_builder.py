"""Few-shot prompting & explicit criteria (Lab 06 STARTER — implement the TODOs).

Public API (must match solution/):

    build_review_prompt(criteria: list[str], few_shot: list[dict]) -> str
    has_explicit_criteria(prompt: str) -> bool
    is_vague_instruction(text: str) -> bool
    severity_rubric() -> dict

These functions build *prompts*; none of them call Claude, so there is no client
to inject.

Grounding (CCAR-F exam guide, Domain 4):
  * Task Statement 4.1 — explicit categorical criteria beat vague instructions;
    false positives erode trust across every category; define severity with
    concrete code examples.
  * Task Statement 4.2 — few-shot examples are the most effective technique for
    consistent, actionable output; 2-4 targeted examples for ambiguous cases that
    show the reasoning for choosing one action over a plausible alternative.
"""

from __future__ import annotations

from typing import Any

__all__ = [
    "build_review_prompt",
    "has_explicit_criteria",
    "is_vague_instruction",
    "severity_rubric",
]


def is_vague_instruction(text: str) -> bool:
    """Return True if ``text`` relies on vague hedges instead of concrete criteria.

    Flag the canonical offenders from Task Statement 4.1 — e.g. "be conservative",
    "only report high-confidence findings", "use your best judgment" — while a
    concrete categorical instruction ("report an issue only when a comment's
    claimed behavior contradicts the code") is NOT vague.

    Suggested approach: keep a list of vague phrase patterns and return True when
    any of them appears (case-insensitive).
    """
    # TODO: detect the vague hedges called out in Task Statement 4.1.
    raise NotImplementedError("is_vague_instruction: flag vague hedge phrases")


def has_explicit_criteria(prompt: str) -> bool:
    """Return True when ``prompt`` states concrete categorical review criteria.

    A prompt qualifies when it names what to REPORT AND what to SKIP (an inclusion
    directive paired with an exclusion directive), or when it lays out an explicit
    severity rubric (two or more distinct severity levels) alongside a report
    directive. A vague prompt ("be conservative and only report high-confidence
    findings") names no categories to exclude, so it must return False.
    """
    # TODO: detect an inclusion directive paired with an exclusion directive (or a
    # severity rubric), NOT merely vague confidence language.
    raise NotImplementedError("has_explicit_criteria: detect categorical criteria")


def severity_rubric() -> dict[str, dict[str, str]]:
    """Map severity levels to concrete definitions, code examples, and actions.

    Return at least three distinct levels (e.g. critical / high / medium / low).
    Each level must carry a DISTINCT, concrete ``code_example`` so classification
    is consistent across runs — the exam guide's remedy for inconsistent severity
    labeling.
    """
    # TODO: return a dict of severity levels -> {definition, code_example, action}.
    raise NotImplementedError("severity_rubric: return concrete severity levels")


def build_review_prompt(criteria: list[str], few_shot: list[dict]) -> str:
    """Compose a code-review system prompt from criteria and few-shot examples.

    Steps:
      1. Validate: ``criteria`` non-empty; ``few_shot`` has 2-4 examples; each
         example has non-empty ``input``, ``output``, and ``why`` keys. Raise
         ValueError otherwise.
      2. Render an explicit categorical criteria section: a REPORT list built from
         ``criteria`` AND a concrete SKIP list of out-of-scope categories.
      3. Render a concrete output format (location, issue, severity, suggested_fix)
         and the severity rubric from ``severity_rubric()``.
      4. Render every few-shot example, showing its input, output, and the WHY
         (reason this choice beats a plausible alternative).
      5. Return the assembled prompt. It must embed every criterion and every
         example, and ``has_explicit_criteria`` must return True for it.

    Args:
        criteria: the categorical REPORT criteria (issue types a finding must match).
        few_shot: 2-4 example dicts, each with keys ``input``, ``output``, ``why``.

    Raises:
        ValueError: on empty criteria, wrong example count, or a malformed example.
    """
    # TODO: implement per the docstring.
    raise NotImplementedError("build_review_prompt: compose criteria + few-shot prompt")
