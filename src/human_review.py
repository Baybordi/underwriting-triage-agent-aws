"""
================================================================
PIPELINE 7 — Human-in-the-loop
================================================================

The agent never makes the final decision — it RECOMMENDS, and a human
underwriter approves or overrides. This file captures that review.

For the PoC the review happens in the console. In production this same step
sits behind a simple underwriter interface (web UI or API), and the record is
written to DynamoDB instead of a local file — the logic is identical.

What it does:
  7.1 Show the agent's recommendation to the underwriter
  7.2 Let them APPROVE it, or OVERRIDE with a different decision
  7.3 Record the review (agent decision, final decision, who, when) to a file
      -> this is the audit trail that feeds future improvement
"""

import json
import time

from logger import get_logger

log = get_logger(__name__)

REVIEW_FILE = "reviews.jsonl"      # local audit trail (one review per line)
VALID = ("QUOTE", "DECLINE", "REFER")


# ============================================================
# 7.3 — record one review to the audit trail
# ============================================================
def _save_review(record):
    with open(REVIEW_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")
    log.info(f"Human review saved: agent={record['agent_decision']} "
             f"final={record['final_decision']} overridden={record['overridden']}")


# ============================================================
# 7.1 + 7.2 — show recommendation, capture approve/override
# ============================================================
def human_review(result, reviewer="underwriter", interactive=True):
    """
    Show the agent's recommendation and capture the underwriter's decision.
    Returns the final (human-approved) result.

    interactive=True  -> ask in the console (local PoC)
    interactive=False -> auto-approve (used for automated tests / batch runs)
    """
    agent_decision = result.get("decision")

    print("\n--- UNDERWRITER REVIEW ---")
    print(f"Agent recommends : {agent_decision}")
    print(f"Reason           : {result.get('reason')}")

    if interactive:
        # 7.2 ask the human
        answer = input("Approve? (press Enter to approve, or type QUOTE/DECLINE/REFER to override): ").strip().upper()
    else:
        answer = ""   # non-interactive = approve

    if answer in VALID and answer != agent_decision:
        final_decision = answer
        overridden = True
    else:
        final_decision = agent_decision
        overridden = False

    # 7.3 record the review
    record = {
        "time": time.strftime("%Y-%m-%d %H:%M:%S"),
        "reviewer": reviewer,
        "agent_decision": agent_decision,
        "final_decision": final_decision,
        "overridden": overridden,
        "reason": result.get("reason"),
    }
    _save_review(record)

    # the human's decision is final
    result["final_decision"] = final_decision
    result["overridden"] = overridden
    return result


# ============================================================
# QUICK TEST (non-interactive so it runs without input)
# ============================================================
if __name__ == "__main__":
    demo = {"decision": "QUOTE", "reason": "Accepted office within limit."}
    out = human_review(demo, interactive=False)
    print("Final decision:", out["final_decision"], "| overridden:", out["overridden"])
    print(f"(review written to {REVIEW_FILE})")
