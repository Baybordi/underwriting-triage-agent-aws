"""
================================================================
PIPELINE 8 — Versioning (governance)
================================================================

Keeps simple version numbers for the parts that affect a decision.
When you change the model, the prompt, or the rules, bump the number here.

Every decision and every evaluation run is stamped with these versions, so a
result can always be traced back to exactly what produced it — and so two
evaluation runs (v1 vs v2) can be compared fairly.

(In production this is where tools like MLflow or Langfuse would track versions.)
"""

VERSION = {
    "config_version": "v1",              # overall version label for this run
    "model": "llama3.2:latest",          # the LLM used
    "embedding_model": "all-MiniLM-L6-v2",
    "prompt_version": "v1",              # bump when the system prompt changes
    "knowledge_base_version": "v1",      # bump when the rule docs change
    "chunking": "heading",               # chunking strategy used
}


def get_version():
    """Return the current version stamp (a copy)."""
    return dict(VERSION)
