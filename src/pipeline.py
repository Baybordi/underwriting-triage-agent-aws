"""
FULL PIPELINE — ties the runtime stages together for one submission.

Order (inside a try/except so nothing can crash — Pipeline 0 resilience):
  2. Input Protection  (input_guard)    -> empty / size / injection / harmful
  3. Data Protection   (data_protection) -> mask PII before the LLM
  4. Agent Decision    (agent)           -> retrieve rules + decide
  6. Output Protection (output_guard)    -> schema / groundedness / harmful -> REFER if bad

Monitoring (Pipeline 10): every stage logs its key events via the shared logger,
so the same information appears on the console now and in CloudWatch on AWS.
"""

import time

from input_guard import check_input
from data_protection import mask_pii
from agent import assess
from output_guard import check_output
from logger import get_logger          # Pipeline 10 — shared logging

log = get_logger(__name__)


def run_pipeline(submission_text):
    """Run one submission through the full runtime chain. Always returns a dict."""
    start = time.time()
    log.info("Pipeline START")

    try:
        # --- Pipeline 2: input protection ---
        guard = check_input(submission_text)
        if not guard["safe"]:
            log.info(f"Input guard BLOCKED -> REFER | reason: {guard['reason']}")
            return {
                "decision": guard["decision"],      # REFER
                "risk_level": None,
                "reason": guard["reason"],
                "stage": "input_guard",
                "rules_used": [],
                "retrieval_similarity": 0,
            }

        # --- Pipeline 3: data protection (mask PII) ---
        masked_text, masked_fields = mask_pii(submission_text)
        if masked_fields:
            log.info(f"PII masked: {masked_fields}")

        # --- Pipeline 4: agent decision ---
        result = assess(masked_text)
        result["stage"] = "agent"
        result["masked_fields"] = masked_fields
        log.info(f"Agent decision: {result['decision']} "
                 f"| retrieval={result.get('retrieval_ms')}ms llm={result.get('llm_ms')}ms")

        # --- Pipeline 6: output protection ---
        result = check_output(result)
        if result.get("output_guard") == "blocked":
            log.info(f"Output guard BLOCKED -> REFER | reason: {result['reason']}")

        total_ms = round((time.time() - start) * 1000)
        log.info(f"Pipeline END -> {result['decision']} | total={total_ms}ms")
        return result

    except Exception as e:
        # --- Pipeline 0: fail safe ---
        log.error(f"Pipeline ERROR -> REFER | {e}")
        return {
            "decision": "REFER",
            "risk_level": None,
            "reason": f"Unexpected error, referred for safety: {e}",
            "stage": "error",
            "rules_used": [],
            "retrieval_similarity": 0,
        }


if __name__ == "__main__":
    text = ("Submission for SME commercial property insurance. Business type: office "
            "(accepted), Manchester, United Kingdom. Sum insured 800000 GBP within limit. "
            "Built 2005. Clean claims, no claims in five years. Fire alarm fitted.")
    out = run_pipeline(text)
    print("\nDecision:", out["decision"], "| stage:", out["stage"])
    print("Reason  :", out["reason"])
