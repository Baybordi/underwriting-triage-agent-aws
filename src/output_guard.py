"""
================================================================
PIPELINE 6 — Output Protection  (the last line of defence)
================================================================

Runs AFTER the agent produces a decision, on every live request.
It makes sure the agent's output is safe and trustworthy before it is shown.

This is the live counterpart of the checks the evaluation only MEASURES:
here we actually BLOCK bad output and force a safe REFER.

Checks (each in its own clearly-separated section below):
  6.1  Schema check        - output has a valid decision / risk / reason
  6.2  Groundedness check  - the reason is based on the retrieved rules
                             (low groundedness = possible hallucination)
  6.5  Harmful content     - the output text is safe / professional
  6.3  Fail-safe           - if any check fails -> force REFER + reason

One function, check_output(result), returns the result either unchanged
(if safe) or overridden to a safe REFER (if not).
"""

import re

# ============================================================
# SETTINGS
# ============================================================
VALID_DECISIONS = ("QUOTE", "DECLINE", "REFER")
GROUNDEDNESS_THRESHOLD = 0.35          # below this -> treat as hallucination
HARMFUL_WORDS = ["kill", "bomb", "terrorist", "racist", "hate"]


# ============================================================
# SECTION 6.1 — SCHEMA CHECK
# "Is the output well-formed (valid decision, has a reason)?"
# ============================================================
def _schema_ok(result):
    if result.get("decision") not in VALID_DECISIONS:
        return False
    if not result.get("reason"):
        return False
    return True


# ============================================================
# SECTION 6.2 — GROUNDEDNESS CHECK (anti-hallucination)
# "Do the reason's words actually come from the retrieved rules?"
# ============================================================
def _tokens(text):
    return set(re.findall(r"[a-z]{4,}", text.lower()))

def _groundedness(result):
    reason_words = _tokens(result.get("reason", ""))
    if not reason_words:
        return 0.0
    rules_text = " ".join(r["text"] for r in result.get("rules_used", []))
    rules_words = _tokens(rules_text)
    return len(reason_words & rules_words) / len(reason_words)


# ============================================================
# SECTION 6.5 — HARMFUL CONTENT CHECK
# "Is the output text safe and professional?"
# ============================================================
def _has_harmful(result):
    text = (result.get("reason", "")).lower()
    return any(word in text for word in HARMFUL_WORDS)


# ============================================================
# SECTION 6.3 — FAIL-SAFE helper: force a safe REFER
# ============================================================
def _force_refer(result, reason):
    result["decision"] = "REFER"
    result["risk_level"] = None
    result["reason"] = reason
    result["output_guard"] = "blocked"
    return result


# ============================================================
# THE OUTPUT GUARD — run all checks in order
# ============================================================
def check_output(result):
    """Validate the agent's output. Return it safe, or overridden to REFER."""

    # 6.1 schema
    if not _schema_ok(result):
        return _force_refer(result, "Output failed schema check. Referred for safety.")

    # 6.5 harmful content
    if _has_harmful(result):
        return _force_refer(result, "Output contained unsafe content. Referred for safety.")

    # 6.2 groundedness (only meaningful when the agent actually used rules)
    grounded = _groundedness(result)
    result["groundedness"] = round(grounded, 2)
    if result.get("rules_used") and grounded < GROUNDEDNESS_THRESHOLD:
        return _force_refer(
            result,
            f"Output not well grounded in the rules (groundedness={grounded:.2f}). "
            "Possible hallucination — referred for safety.",
        )

    # all checks passed
    result["output_guard"] = "passed"
    return result


# ============================================================
# QUICK TEST
# ============================================================
if __name__ == "__main__":
    # a grounded, valid output -> should pass
    good = {
        "decision": "QUOTE",
        "risk_level": "Low",
        "reason": "Business type is an accepted office within the sum insured limit.",
        "rules_used": [{"text": "Accepted business types include offices within the sum insured limit."}],
    }
    # an invalid output -> should be forced to REFER
    bad = {"decision": "MAYBE", "reason": "", "rules_used": []}

    print("GOOD ->", check_output(dict(good))["decision"], "| guard:", check_output(dict(good))["output_guard"])
    print("BAD  ->", check_output(dict(bad))["decision"], "| guard:", check_output(dict(bad))["output_guard"])
