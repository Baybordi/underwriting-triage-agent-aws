"""
================================================================
METRICS — per-pipeline observability (CloudWatch custom metrics)
================================================================

Records the numbers an AI platform team needs to watch the agent:

  PER-REQUEST (runtime):
    - InputGuardLatencyMs     : time to screen/validate the input
    - RetrievalLatencyMs      : time for the RAG search
    - LLMLatencyMs            : time for the model to answer
    - OutputGuardLatencyMs    : time to check the output
    - TotalLatencyMs          : end-to-end
    - GuardrailPassed         : 1 if output passed guardrails, 0 if blocked
    - InjectionBlocked        : 1 if input injection was caught
    - Decision                : QUOTE / DECLINE / REFER (as a dimension)
    - CostUSD                 : LLM cost of the request

  EVALUATION (offline):
    - Accuracy, PrecisionQUOTE/DECLINE/REFER, RecallQUOTE/DECLINE/REFER
    - RetrievalRecallAtK, MRR, Hallucinations

Where it sends:
  - AWS   (USE_CLOUDWATCH_METRICS=true) -> CloudWatch custom metrics (dashboards)
  - local (default)                     -> prints to console only (no-op to AWS)

Namespace in CloudWatch: "InsuranceAgent"
"""

import os
import time

NAMESPACE = "InsuranceAgent"
USE_CLOUDWATCH = os.environ.get("USE_CLOUDWATCH_METRICS", "false").lower() == "true"
REGION = os.environ.get("AWS_DEFAULT_REGION", "eu-west-2")

_client = None
def _cw():
    """Lazy CloudWatch client (only created if sending to AWS)."""
    global _client
    if _client is None:
        import boto3
        _client = boto3.client("cloudwatch", region_name=REGION)
    return _client


# ============================================================
# SEND ONE METRIC
# ============================================================
def put_metric(name, value, unit="None", dimensions=None):
    """Record one metric. Sends to CloudWatch on AWS, else prints locally."""
    dims = dimensions or {}
    if USE_CLOUDWATCH:
        try:
            _cw().put_metric_data(
                Namespace=NAMESPACE,
                MetricData=[{
                    "MetricName": name,
                    "Value": float(value),
                    "Unit": unit,
                    "Dimensions": [{"Name": k, "Value": str(v)} for k, v in dims.items()],
                }],
            )
        except Exception as e:
            print(f"[metrics] could not send {name}: {e}")
    else:
        extra = f" {dims}" if dims else ""
        print(f"[metric] {name} = {value} {unit}{extra}")


# ============================================================
# A SIMPLE STAGE TIMER  (use with 'with')
# ============================================================
class Timer:
    """Times a block of code and records it as a latency metric.

    Usage:
        with Timer("RetrievalLatencyMs"):
            rules = retrieve_rules(text)
    """
    def __init__(self, metric_name, dimensions=None):
        self.metric_name = metric_name
        self.dimensions = dimensions

    def __enter__(self):
        self._start = time.time()
        return self

    def __exit__(self, *exc):
        ms = round((time.time() - self._start) * 1000)
        put_metric(self.metric_name, ms, unit="Milliseconds", dimensions=self.dimensions)
        self.ms = ms
        return False   # don't swallow exceptions


# ============================================================
# CONVENIENCE: record the whole request's metrics at once
# ============================================================
def record_request_metrics(result):
    """Record the per-request metrics from a finished pipeline result."""
    decision = result.get("decision", "UNKNOWN")
    put_metric("RequestCount", 1, "Count", {"Decision": decision})

    if result.get("retrieval_ms") is not None:
        put_metric("RetrievalLatencyMs", result["retrieval_ms"], "Milliseconds")
    if result.get("llm_ms") is not None:
        put_metric("LLMLatencyMs", result["llm_ms"], "Milliseconds")

    # guardrail outcome: 1 passed, 0 blocked
    passed = 0 if result.get("output_guard") == "blocked" else 1
    put_metric("GuardrailPassed", passed, "Count")

    # injection caught at input stage
    if result.get("stage") == "input_guard":
        put_metric("InjectionBlocked", 1, "Count")

    # refer rate: 1 if this request was referred, 0 otherwise
    #            (average of this metric on the dashboard = the REFER rate)
    put_metric("IsRefer", 1 if decision == "REFER" else 0, "Count")

    # error: 1 if the pipeline failed
    if result.get("stage") == "error":
        put_metric("ErrorCount", 1, "Count")

    # live groundedness (hallucination signal), when the agent produced an answer
    if result.get("groundedness") is not None:
        put_metric("Groundedness", result["groundedness"], "None")

    # cost + tokens of the LLM call (attached by the pipeline from llm.LAST_USAGE)
    if result.get("cost_usd") is not None:
        put_metric("CostUSD", result["cost_usd"], "None")
    if result.get("input_tokens") is not None:
        put_metric("InputTokens", result["input_tokens"], "Count")
    if result.get("output_tokens") is not None:
        put_metric("OutputTokens", result["output_tokens"], "Count")

    # data-protection signal: how many PII fields were masked
    if result.get("masked_fields"):
        put_metric("PIIMaskedCount", len(result["masked_fields"]), "Count")


if __name__ == "__main__":
    # demo (local prints)
    with Timer("RetrievalLatencyMs"):
        time.sleep(0.05)
    put_metric("GuardrailPassed", 1, "Count")
    put_metric("RequestCount", 1, "Count", {"Decision": "QUOTE"})
    print("metrics demo done (USE_CLOUDWATCH_METRICS =", USE_CLOUDWATCH, ")")
