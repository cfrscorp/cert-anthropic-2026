"""Reference implementation: Agent SDK hooks and workflow enforcement.

This module implements the four programmatic-enforcement primitives from Task
Statements 1.5 (hooks for interception and normalization) and 1.4 (prerequisite
gates and structured handoffs) of the CCAR-F exam guide:

- ``post_tool_use_normalize`` — a ``PostToolUse``-style hook that rewrites a raw
  tool result into one canonical shape *before the model ever sees it*, so the
  agent reasons over uniform ISO-8601 timestamps and human-readable status
  labels instead of a mix of Unix ints, ISO strings, and numeric HTTP codes.
- ``intercept_tool_call`` — an outgoing-tool-call interception hook that blocks a
  policy-violating action (a refund above ``refund_limit``) and redirects it to
  human escalation. This is a *deterministic* guarantee: the rule holds on every
  call regardless of how the model was prompted.
- ``PrerequisiteGate`` — enforces ordering: ``process_refund`` is blocked until
  ``get_customer`` has returned a *verified* ``customer_id``. This is the
  programmatic answer to Sample Question 1 (a prerequisite gate beats a
  prompt/few-shot instruction when errors have financial consequences).
- ``build_handoff`` — compiles a structured escalation summary for a human agent
  who has no access to the conversation transcript.

Why hooks instead of prompt instructions? Prompt-based compliance is
*probabilistic*: it has a non-zero failure rate that is unacceptable for identity
verification and money movement. Hooks run in code, so they give *deterministic*
guarantees.

This is an importable module (no shell entry point), so it carries docstrings but
is exempt from the PEP 723 / argparse script conventions.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

__all__ = [
    "post_tool_use_normalize",
    "intercept_tool_call",
    "PrerequisiteGate",
    "build_handoff",
]


# --------------------------------------------------------------------------- #
# PostToolUse normalization hook (Task Statement 1.5)
# --------------------------------------------------------------------------- #

def _timestamp_to_iso(value: Any) -> str:
    """Convert a heterogeneous timestamp into a canonical ISO-8601 UTC string.

    Accepts a Unix epoch (int/float seconds) or an ISO-8601 string (with a
    trailing ``Z`` or an explicit offset, or naive — assumed UTC). Returns a
    timezone-aware ISO-8601 string so every tool's timestamps compare directly.
    """
    # bool is an int subclass; reject it so True/False can't masquerade as epoch.
    if isinstance(value, bool):
        raise TypeError(f"Cannot interpret {value!r} as a timestamp.")
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc).isoformat()
    if isinstance(value, str):
        text = value.strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.isoformat()
    raise TypeError(f"Unsupported timestamp type: {type(value).__name__}")


def _status_to_label(value: Any) -> str:
    """Map a numeric HTTP-style status code (or existing label) to a label.

    2xx -> ``"success"``, 3xx -> ``"redirect"``, 4xx -> ``"client_error"``,
    5xx -> ``"server_error"``. A string is passed through lowercased/stripped so
    tools that already return a label ("ok", "success") stay stable.
    """
    if isinstance(value, bool):
        raise TypeError(f"Cannot interpret {value!r} as a status code.")
    if isinstance(value, int):
        if 200 <= value < 300:
            return "success"
        if 300 <= value < 400:
            return "redirect"
        if 400 <= value < 500:
            return "client_error"
        if 500 <= value < 600:
            return "server_error"
        return "unknown"
    if isinstance(value, str):
        return value.strip().lower()
    raise TypeError(f"Unsupported status type: {type(value).__name__}")


def post_tool_use_normalize(tool_name: str, result: dict[str, Any]) -> dict[str, Any]:
    """PostToolUse hook: normalize one raw tool result into a canonical shape.

    Different MCP tools report time and status differently: one returns a Unix
    epoch int, another an ISO-8601 string, another an HTTP-style numeric code.
    Feeding that heterogeneity to the model wastes tokens and invites
    misinterpretation. This hook runs *after* the tool and *before* the model
    processes the result, rewriting the two volatile fields into canonical forms:

    - ``timestamp`` -> ISO-8601 UTC string (from Unix int or ISO string).
    - ``status``    -> a human-readable label (from a numeric code or a label).

    All other fields are preserved unchanged, plus a ``source_tool`` field is
    added so downstream reasoning keeps provenance. Fields that are absent are
    left absent — the hook never fabricates data.

    Args:
        tool_name: The tool that produced ``result`` (recorded as ``source_tool``).
        result: The raw tool result mapping.

    Returns:
        A new dict (the original is not mutated) in canonical shape.
    """
    normalized: dict[str, Any] = dict(result)
    normalized["source_tool"] = tool_name
    if "timestamp" in result:
        normalized["timestamp"] = _timestamp_to_iso(result["timestamp"])
    if "status" in result:
        normalized["status"] = _status_to_label(result["status"])
    return normalized


# --------------------------------------------------------------------------- #
# Tool-call interception hook (Task Statement 1.5)
# --------------------------------------------------------------------------- #

def intercept_tool_call(
    tool_name: str,
    tool_input: dict[str, Any],
    *,
    refund_limit: float = 500,
) -> dict[str, Any]:
    """Interception hook: allow a tool call or block it and redirect to a human.

    Business rule: a ``process_refund`` call whose amount exceeds ``refund_limit``
    is a policy violation and must never execute autonomously. Enforcing this in
    a hook makes it *deterministic* — the ceiling holds on every call no matter
    what the model was prompted to do (Task Statement 1.5: choose hooks over
    prompt-based enforcement when a rule requires guaranteed compliance).

    Args:
        tool_name: The outgoing tool the model wants to call.
        tool_input: The proposed arguments; a refund amount is read from
            ``"amount"`` (falling back to ``"refund_amount"``).
        refund_limit: Inclusive auto-approval ceiling; amounts strictly greater
            than this are blocked. Defaults to $500.

    Returns:
        ``{"action": "allow"}`` to permit the call, or
        ``{"action": "block", "redirect": "escalate_to_human", "reason": ...}``
        to stop it and hand off to human escalation.
    """
    if tool_name == "process_refund":
        amount = tool_input.get("amount", tool_input.get("refund_amount", 0))
        if amount > refund_limit:
            return {
                "action": "block",
                "redirect": "escalate_to_human",
                "reason": (
                    f"Refund of ${amount} exceeds the ${refund_limit} "
                    "auto-approval limit; redirecting to human escalation."
                ),
            }
    return {"action": "allow"}


# --------------------------------------------------------------------------- #
# Prerequisite gate (Task Statement 1.4 / Sample Question 1)
# --------------------------------------------------------------------------- #

class PrerequisiteGate:
    """Blocks protected tools until a prerequisite step has verified identity.

    Sample Question 1 in the exam guide describes an agent that sometimes skips
    ``get_customer`` and refunds the wrong account. The correct fix is *not* a
    stronger prompt or more few-shot examples (both only lower a probabilistic
    failure rate) — it is a programmatic prerequisite that makes the unsafe path
    impossible.

    This gate records tool results as they come back and refuses ``process_refund``
    (or any configured protected tool) until ``get_customer`` has returned a
    *verified* ``customer_id``.

    Usage::

        gate = PrerequisiteGate()
        assert gate.check("process_refund") is False       # nothing verified yet
        gate.record_tool_result("get_customer",
                                {"customer_id": "C-42", "verified": True})
        assert gate.check("process_refund") is True         # now allowed
    """

    def __init__(
        self,
        *,
        protected_tools: tuple[str, ...] = ("process_refund", "lookup_order"),
        prerequisite_tool: str = "get_customer",
    ) -> None:
        """Configure which tools are gated behind which verification step.

        Args:
            protected_tools: Tools that stay blocked until identity is verified.
                Defaults to ``process_refund`` and ``lookup_order`` (both act on a
                specific account, so both need a verified customer first).
            prerequisite_tool: The tool whose verified result unlocks the gate.
        """
        self._protected_tools = tuple(protected_tools)
        self._prerequisite_tool = prerequisite_tool
        self._verified_customer_id: str | None = None

    @property
    def verified_customer_id(self) -> str | None:
        """The verified customer id recorded so far, or ``None`` if not yet set."""
        return self._verified_customer_id

    def record_tool_result(self, name: str, result: dict[str, Any]) -> None:
        """Record a tool result, unlocking the gate on a verified prerequisite.

        Only a ``prerequisite_tool`` result that carries a truthy ``customer_id``
        *and* ``verified is True`` flips the gate open. An unverified or empty
        ``get_customer`` result (e.g. multiple/no matches) leaves it closed.
        """
        if name != self._prerequisite_tool:
            return
        customer_id = result.get("customer_id")
        if customer_id and result.get("verified") is True:
            self._verified_customer_id = customer_id

    def check(self, tool_name: str) -> bool:
        """Return whether ``tool_name`` is allowed to run right now.

        Protected tools are allowed only once a verified customer id exists;
        every other tool is always allowed.
        """
        if tool_name in self._protected_tools:
            return self._verified_customer_id is not None
        return True


# --------------------------------------------------------------------------- #
# Structured handoff (Task Statement 1.4)
# --------------------------------------------------------------------------- #

def build_handoff(context: dict[str, Any]) -> dict[str, Any]:
    """Compile a structured escalation summary for a human agent.

    A human picking up an escalation has no access to the conversation
    transcript, so the handoff must carry the facts they need to act: who the
    customer is, what went wrong, the money involved, and the recommended next
    step (Task Statement 1.4).

    Args:
        context: Case context; recognized keys are ``customer_id``,
            ``root_cause``, ``refund_amount``, and ``recommended_action``.
            Missing keys are surfaced as ``None`` rather than dropped, so the
            receiving human can see exactly what is unknown.

    Returns:
        A dict with the required handoff fields plus ``escalated_to: "human"``.
    """
    return {
        "customer_id": context.get("customer_id"),
        "root_cause": context.get("root_cause"),
        "refund_amount": context.get("refund_amount"),
        "recommended_action": context.get("recommended_action"),
        "escalated_to": "human",
    }
