"""Few-shot prompting & explicit criteria (Lab 06 reference solution).

Public API (identical in starter/ and solution/):

    build_review_prompt(criteria: list[str], few_shot: list[dict]) -> str
        Compose a code-review system prompt with (a) an explicit *categorical*
        criteria section (which issues to REPORT vs which to SKIP), (b) a concrete
        output format, and (c) 2-4 few-shot examples. Each example shows an input,
        the desired output, and WHY that choice beats a plausible alternative.

    has_explicit_criteria(prompt: str) -> bool
        True when a prompt contains concrete *categorical* criteria (an inclusion
        directive paired with an exclusion directive, or an explicit severity
        rubric), rather than only vague confidence hedges.

    is_vague_instruction(text: str) -> bool
        True when a fragment leans on vague hedges ("be conservative", "only
        high-confidence findings", "use your judgment") that the exam guide calls
        out as insufficient for improving precision.

    severity_rubric() -> dict
        A rubric mapping each severity level to a concrete definition, a real code
        example, and the expected reviewer action.

These functions build *prompts*; none of them call Claude, so there is no client
to inject. The optional live check in the test suite grades a built prompt with
the shared ``grade`` helper.

Grounding (CCAR-F exam guide, Domain 4):
  * Task Statement 4.1 — explicit categorical criteria beat vague instructions;
    false positives erode trust across every category; define severity with
    concrete code examples.
  * Task Statement 4.2 — few-shot examples are the most effective technique for
    consistent, actionable output; 2-4 targeted examples for ambiguous cases that
    show the reasoning for choosing one action over a plausible alternative.
"""

from __future__ import annotations

import re
from typing import Any

__all__ = [
    "build_review_prompt",
    "has_explicit_criteria",
    "is_vague_instruction",
    "severity_rubric",
]

# --------------------------------------------------------------------------- #
# Vague-instruction detection (Task Statement 4.1)                            #
# --------------------------------------------------------------------------- #
# Phrases the exam guide flags as *insufficient* substitutes for categorical
# criteria. They ask the model to self-assess confidence or "judgment" instead
# of naming which issue categories to include or exclude.
_VAGUE_PATTERNS: tuple[str, ...] = (
    r"be conservative",
    r"only\s+(report|flag|surface)?\s*high[\s-]*confidence",
    r"high[\s-]*confidence\s+(findings|issues|only)",
    r"use your (best )?judg?ment",
    r"when in doubt",
    r"be (thorough|careful|cautious)\b",
    r"only (report|flag) (issues|things|what) you(?:'re| are) (sure|confident)",
    r"flag anything (suspicious|that looks off|questionable)",
    r"check that .* (are|is) (accurate|correct)",  # "check that comments are accurate"
)

# Inclusion vs exclusion directives — the two halves of a *categorical* rule.
_INCLUSION_RE = re.compile(r"\b(report|flag|raise|catch)\b", re.IGNORECASE)
_EXCLUSION_RE = re.compile(
    r"\b(skip|ignore|exclude)\b|do\s*n['o]?t\s+(report|flag|raise)",
    re.IGNORECASE,
)
# Severity labels; two or more distinct ones signal an explicit severity rubric.
_SEVERITY_RE = re.compile(
    r"\b(critical|blocker|high|medium|moderate|low|warning|info)\b", re.IGNORECASE
)


def is_vague_instruction(text: str) -> bool:
    """Return True if ``text`` relies on vague hedges instead of concrete criteria.

    The canonical offenders from Task Statement 4.1 — "be conservative", "only
    report high-confidence findings", "use your best judgment" — all match. A
    concrete categorical instruction ("report an issue only when a comment's
    claimed behavior contradicts the code") does not.
    """
    low = text.lower()
    return any(re.search(pat, low) for pat in _VAGUE_PATTERNS)


def has_explicit_criteria(prompt: str) -> bool:
    """Return True when ``prompt`` states concrete categorical review criteria.

    A prompt qualifies when it pairs an *inclusion* directive (report/flag …)
    with an *exclusion* directive (skip/ignore/do not report …) — i.e. it names
    what to REPORT **and** what to SKIP — or when it lays out an explicit severity
    rubric (two or more distinct severity levels) alongside a report directive.

    Vague prompts fail this check: "be conservative and only report
    high-confidence findings" names no categories to exclude, so it returns False.
    """
    has_inclusion = bool(_INCLUSION_RE.search(prompt))
    has_exclusion = bool(_EXCLUSION_RE.search(prompt))
    distinct_severities = {m.lower() for m in _SEVERITY_RE.findall(prompt)}

    if has_inclusion and has_exclusion:
        return True
    if has_inclusion and len(distinct_severities) >= 2:
        return True
    return False


# --------------------------------------------------------------------------- #
# Severity rubric with concrete code examples (Task Statement 4.1)            #
# --------------------------------------------------------------------------- #
def severity_rubric() -> dict[str, dict[str, str]]:
    """Map severity levels to concrete definitions, code examples, and actions.

    Each level carries a distinct real code example so classification is
    consistent — the exam guide's remedy for models that rate the same defect
    differently across runs. Levels are ordered most-severe first.
    """
    return {
        "critical": {
            "definition": (
                "A defect that causes data loss, a security breach, or a crash on "
                "a common code path in production."
            ),
            "code_example": (
                'cursor.execute(f"SELECT * FROM users WHERE id = {user_id}")  '
                "# unsanitized input -> SQL injection"
            ),
            "action": "Block the merge; must be fixed before release.",
        },
        "high": {
            "definition": (
                "A logic bug that produces wrong results or an unhandled error on "
                "a realistic input, but is not exploitable or catastrophic."
            ),
            "code_example": (
                "def average(xs):\n"
                "    return sum(xs) / len(xs)  # ZeroDivisionError on an empty list"
            ),
            "action": "Request changes; fix before merge.",
        },
        "medium": {
            "definition": (
                "A correctness or maintainability risk that only surfaces in an "
                "edge case or degrades behavior without breaking it."
            ),
            "code_example": (
                "cache[key] = value  # unbounded dict; memory grows without eviction"
            ),
            "action": "Comment; fix in this PR or a fast follow-up.",
        },
        "low": {
            "definition": (
                "A minor improvement with no behavioral impact (a clarifying "
                "rename, a redundant branch). Report only when it aids a real fix."
            ),
            "code_example": (
                "if is_ready == True:  # redundant comparison; `if is_ready:` reads better"
            ),
            "action": "Optional; a non-blocking nit.",
        },
    }


# --------------------------------------------------------------------------- #
# Prompt composition (Task Statements 4.1 + 4.2)                              #
# --------------------------------------------------------------------------- #
# Concrete, categorical SKIP list. Precision beats recall: a false positive in
# one category erodes trust in every category, so out-of-scope items are named
# explicitly rather than left to a vague "be conservative".
_DEFAULT_SKIP = (
    "Subjective style preferences already enforced by the formatter or linter",
    "Naming or formatting nits that do not change behavior",
    "Local patterns that are consistent with the surrounding file",
    "Anything that does not clearly match a REPORT category (when unsure, SKIP)",
)

_OUTPUT_FIELDS = ("location", "issue", "severity", "suggested_fix")


def _render_example(index: int, ex: dict[str, Any]) -> str:
    """Render one few-shot example, requiring input / output / why."""
    missing = [k for k in ("input", "output", "why") if not ex.get(k)]
    if missing:
        raise ValueError(
            f"few_shot[{index}] is missing required key(s) {missing}; each example "
            "must include 'input', 'output', and 'why' (the reason this choice "
            "beats a plausible alternative)."
        )
    title = ex.get("title", f"Example {index + 1}")
    return (
        f"### {title}\n"
        f"Input:\n{ex['input']}\n\n"
        f"Output:\n{ex['output']}\n\n"
        f"Why this over the plausible alternative:\n{ex['why']}\n"
    )


def build_review_prompt(criteria: list[str], few_shot: list[dict]) -> str:
    """Compose a code-review system prompt from criteria and few-shot examples.

    Args:
        criteria: the categorical REPORT criteria — the issue types a finding must
            match to be reported (e.g. "a comment's claimed behavior contradicts
            the code", "user input reaches a query without sanitization"). Must be
            non-empty.
        few_shot: 2-4 example dicts, each with keys ``input``, ``output``, and
            ``why`` (the reasoning for choosing this action over a plausible
            alternative). Ambiguous cases and the exact output format belong here.

    Returns:
        A system prompt string that embeds every criterion and every example, a
        concrete output format, and an explicit SKIP list. ``has_explicit_criteria``
        returns True for the result.

    Raises:
        ValueError: if ``criteria`` is empty, if ``few_shot`` is not 2-4 examples,
            or if any example lacks input/output/why.
    """
    if not criteria:
        raise ValueError("criteria must be a non-empty list of REPORT categories.")
    if not (2 <= len(few_shot) <= 4):
        raise ValueError(
            f"few_shot must contain 2-4 examples (got {len(few_shot)}); the exam "
            "guide recommends 2-4 targeted examples for ambiguous cases."
        )

    report_block = "\n".join(f"- {c}" for c in criteria)
    skip_block = "\n".join(f"- {s}" for s in _DEFAULT_SKIP)
    fields = ", ".join(_OUTPUT_FIELDS)
    examples_block = "\n".join(
        _render_example(i, ex) for i, ex in enumerate(few_shot)
    )
    rubric = severity_rubric()
    severity_block = "\n".join(
        f"- {level}: {info['definition']}\n"
        f"  example: {info['code_example']}"
        for level, info in rubric.items()
    )

    return f"""You are an automated code reviewer. Follow the criteria below EXACTLY.

Precision matters more than recall. A false positive erodes developer trust in
every category, so report an issue ONLY when it clearly matches a REPORT category.
When you are unsure, SKIP it — do not hedge with a low-confidence guess.

## Criteria

### REPORT an issue only when it matches one of these categories:
{report_block}

### SKIP (do NOT report) — these are out of scope:
{skip_block}

## Severity levels
Classify every reported issue using this rubric:
{severity_block}

## Output format
Report each finding with exactly these fields: {fields}.
- location: <file>:<line>
- issue: <one concrete sentence>
- severity: <critical | high | medium | low>
- suggested_fix: <the specific change to make>
If there are no reportable issues, output exactly: No issues found.

## Examples
Study these. Match the output format and the reasoning style precisely, including
how ambiguous cases are decided.

{examples_block}"""
