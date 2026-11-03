"""
================================================================
PIPELINE 8 — Versioning (governance)
================================================================

Keeps simple version numbers for the parts that affect a decision.
When you change the prompt or the rules, bump the number here.

The MODEL NAME is read automatically from llm.py (whichever provider/model is
active), so it is always correct without editing it by hand. Only the manual
labels below (version, prompt, knowledge base) are a human choice.

Every evaluation run is stamped with these versions, so results can be traced
back to exactly what produced them, and two runs (v1 vs v2) compared fairly.

(In production this is where tools like MLflow or Langfuse would track versions.)
"""

import llm   # to read the active provider + model automatically


# --- manual labels (your choice when something changes) ---
CONFIG_VERSION = "v2"                        # bump when you start a new experiment
PROMPT_VERSION = "v1"                        # bump when the system prompt changes
KNOWLEDGE_BASE_VERSION = "v1"                # bump when the rule docs change
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
CHUNKING = "heading"


def _active_model():
    """Read the model name automatically from llm.py, based on the active provider."""
    if llm.PROVIDER == "ollama":
        return llm.OLLAMA_MODEL
    if llm.PROVIDER == "anthropic":
        return llm.ANTHROPIC_MODEL
    if llm.PROVIDER == "bedrock":
        return llm.BEDROCK_MODEL
    return llm.PROVIDER


def get_version():
    """Return the current version stamp (model name filled in automatically)."""
    return {
        "config_version": CONFIG_VERSION,
        "provider": llm.PROVIDER,            # e.g. "anthropic"
        "model": _active_model(),            # auto-detected, always correct
        "embedding_model": EMBEDDING_MODEL,
        "prompt_version": PROMPT_VERSION,
        "knowledge_base_version": KNOWLEDGE_BASE_VERSION,
        "chunking": CHUNKING,
    }
