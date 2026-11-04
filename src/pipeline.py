"""
FULL PIPELINE — ties the runtime stages together for one submission.

Order (inside a try/except so nothing can crash — Pipeline 0 resilience):
  2. Input Protection  (input_guard)    -> empty / size / injection / harmful
  3. Data Protection   (data_protection) -> mask PII before the LLM
  4. Agent Decision    (agent)           -> retrieve rules + decide
  6. Output Protection (output_guard)    -> schema / groundedness / harmful -> REFER if bad

Traceability:
  - Every run gets a short REQUEST ID, printed on every log line of that run,
    stored on the audit record, and tagged on the metrics -> one run is traceable
    across logs + DynamoDB + CloudWatch metrics.
  - SOURCE tells whether the request came from the Streamlit app or a terminal run.
  - The decision VERSION (model/prompt/KB) is logged for governance.
"""

import time
import uuid

from input_guard import check_input
from data_protection import mask_pii
from agent import assess
from output_guard import check_output
from logger import get_logger
from audit import record_decision
from metrics import Timer, put_metric, record_request_metrics
from version import get_version
import llm

log = get_logger(__name__)


def run_pipeline(submission_text, source="terminal"):
    """Run one submission through the full runtime chain. Always returns a dict.
    `source` = where the request came from: 'streamlit' or 'terminal'."""
    request_id = uuid.uuid4().hex[:8]          # short id for this run
    tag = f"[{request_id}][{source}]"          # prefix for every log line
    start = time.time()
    log.info(f"{tag} Pipeline START | version={get_version()['config_version']}")

    def finish(result):
        """Attach trace info, audit, and metrics — used at every exit."""
        result["request_id"] = request_id
        result["source"] = source
        result["version"] = get_version()["config_version"]
        record_decision(submission_text, result)
        record_request_metrics(result)
        return result

    try:
        # --- Pipeline 2: input protection (timed) ---
        with Timer("InputGuardLatencyMs"):
            guard = check_input(submission_text)
        if not guard["safe"]:
            log.info(f"{tag} Input guard BLOCKED -> REFER | {guard['reason']}")
            return finish({
                "decision": guard["decision"],
                "risk_level": None,
                "reason": guard["reason"],
                "stage": "input_guard",
                "rules_used": [],
                "retrieval_similarity": 0,
            })

        # --- Pipeline 3: data protection (mask PII) ---
        masked_text, masked_fields = mask_pii(submission_text)
        if masked_fields:
            log.info(f"{tag} PII masked: {masked_fields}")

        # --- Pipeline 4: agent decision ---
        result = assess(masked_text)
        result["stage"] = "agent"
        result["masked_fields"] = masked_fields
        log.info(f"{tag} Agent decision: {result['decision']} "
                 f"| retrieval={result.get('retrieval_ms')}ms llm={result.get('llm_ms')}ms")

        # --- Pipeline 6: output protection (timed) ---
        with Timer("OutputGuardLatencyMs"):
            result = check_output(result)
        if result.get("output_guard") == "blocked":
            log.info(f"{tag} Output guard BLOCKED -> REFER | {result['reason']}")

        total_ms = round((time.time() - start) * 1000)
        log.info(f"{tag} Pipeline END -> {result['decision']} | total={total_ms}ms")

        # cost + tokens from the last LLM call
        result["cost_usd"] = llm.LAST_USAGE.get("cost_usd")
        result["input_tokens"] = llm.LAST_USAGE.get("input_tokens")
        result["output_tokens"] = llm.LAST_USAGE.get("output_tokens")

        put_metric("TotalLatencyMs", total_ms, "Milliseconds")
        return finish(result)

    except Exception as e:
        # --- Pipeline 0: fail safe ---
        log.error(f"{tag} Pipeline ERROR -> REFER | {e}")
        return finish({
            "decision": "REFER",
            "risk_level": None,
            "reason": f"Unexpected error, referred for safety: {e}",
            "stage": "error",
            "rules_used": [],
            "retrieval_similarity": 0,
        })


if __name__ == "__main__":
    text = ("Submission for SME commercial property insurance. Business type: office "
            "(accepted), Manchester, United Kingdom. Sum insured 800000 GBP within limit. "
            "Built 2005. Clean claims, no claims in five years. Fire alarm fitted.")
    out = run_pipeline(text, source="terminal")
    print("\nDecision:", out["decision"], "| request_id:", out["request_id"])
    print("Reason  :", out["reason"])
