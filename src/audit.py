"""
================================================================
AUDIT TRAIL  (used by Pipeline 6 output + Pipeline 7 human review)
================================================================

Writes one record per decision so every outcome is traceable — a governance
requirement (FCA / EU AI Act).

Two destinations, chosen by environment:
  - AWS   (USE_DYNAMODB=true) -> writes to a DynamoDB table (durable, queryable)
  - local (default)          -> appends to a local file (audit_log.jsonl)

Same record either way; only the storage differs (a one-setting switch).
"""

import os
import json
import time
import uuid

from logger import get_logger

log = get_logger(__name__)

USE_DYNAMODB = os.environ.get("USE_DYNAMODB", "false").lower() == "true"
DYNAMO_TABLE = os.environ.get("DYNAMO_TABLE", "underwriting_audit")
LOCAL_AUDIT_FILE = "audit_log.jsonl"


def record_decision(submission_text, result):
    """Save one decision record to the audit trail (DynamoDB on AWS, file locally)."""
    record = {
        "id": str(uuid.uuid4()),                      # unique key
        "request_id": result.get("request_id", ""),   # same id as in the logs (correlation)
        "source": result.get("source", ""),           # streamlit / terminal
        "version": result.get("version", ""),          # which config/model version decided
        "time": time.strftime("%Y-%m-%d %H:%M:%S"),
        "decision": result.get("decision"),
        "risk_level": result.get("risk_level"),
        "reason": result.get("reason"),
        "stage": result.get("stage"),
        "retrieval_similarity": str(result.get("retrieval_similarity", 0)),
        "submission": submission_text[:500],          # trimmed for storage
    }

    if USE_DYNAMODB:
        _write_dynamodb(record)
    else:
        _write_local(record)

    log.info(f"[{record['request_id']}][{record['source']}] "
             f"Audit recorded: {record['id']} -> {record['decision']}")
    return record


# ------------------------------------------------------------
def _write_local(record):
    with open(LOCAL_AUDIT_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")


def _write_dynamodb(record):
    import boto3
    table = boto3.resource("dynamodb").Table(DYNAMO_TABLE)
    table.put_item(Item=record)


if __name__ == "__main__":
    demo = {"decision": "QUOTE", "risk_level": "Low", "reason": "test",
            "stage": "agent", "retrieval_similarity": 0.65}
    rec = record_decision("Office in London, sum insured 800000.", demo)
    print("Recorded:", rec["id"], "->", rec["decision"])
    print(f"(written to {'DynamoDB' if USE_DYNAMODB else LOCAL_AUDIT_FILE})")
