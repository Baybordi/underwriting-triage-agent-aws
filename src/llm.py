"""
LLM WRAPPER — one place that talks to the language model.

The rest of the agent only calls call_llm(); it never cares which provider is used.
Switch provider by changing PROVIDER below.

Providers:
  - "ollama"    : free, local (llama3.2)      -> active now, for testing
  - "anthropic" : Claude via Anthropic API    -> needs ANTHROPIC_API_KEY
  - "bedrock"   : Claude via AWS Bedrock       -> needs AWS credentials

RESILIENCE (Pipeline 0) lives here, because the LLM call is the most likely
thing to fail (network, rate limits, timeouts):
  - timeout    : each call is given a time limit
  - retry      : a failed call is retried a few times with a growing wait (backoff)
  - fallback   : if the primary provider still fails, try a backup provider once
  - if everything fails, raise -> the pipeline's try/except turns it into a safe REFER

After every successful call, LAST_USAGE holds the tokens + cost of that call.
"""

import os
import time

# ============================================================
# SETTINGS
# ============================================================
PROVIDER = "ollama"                       # "ollama" | "anthropic" | "bedrock"
FALLBACK_PROVIDER = None                  # e.g. "anthropic" — tried if PROVIDER fails; None = no fallback

OLLAMA_MODEL = "llama3.2:latest"
ANTHROPIC_MODEL = "claude-sonnet-4-5"
BEDROCK_MODEL = "anthropic.claude-3-5-sonnet-20241022-v2:0"

# resilience settings
TIMEOUT_SECONDS = 60       # max time for one call
MAX_RETRIES = 2            # extra attempts after the first (so 3 tries total)
BACKOFF_SECONDS = 2        # wait grows: 2s, 4s, ...

# pricing (per 1M tokens, USD) for the Claude model
PRICE_INPUT_PER_M = 3.0
PRICE_OUTPUT_PER_M = 15.0

LAST_USAGE = {"input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0}


# ============================================================
# PUBLIC FUNCTION — call_llm (with retry + fallback)
# ============================================================
def call_llm(prompt, system=""):
    """Call the LLM with retries; if the primary provider keeps failing,
    try the fallback provider once. Raise only if everything fails."""
    try:
        return _call_with_retry(PROVIDER, prompt, system)
    except Exception as primary_error:
        if FALLBACK_PROVIDER:
            print(f"[llm] primary '{PROVIDER}' failed, trying fallback "
                  f"'{FALLBACK_PROVIDER}': {primary_error}")
            return _call_with_retry(FALLBACK_PROVIDER, prompt, system)
        raise   # no fallback -> let the pipeline fail safe to REFER


# ============================================================
# RETRY + BACKOFF wrapper
# ============================================================
def _call_with_retry(provider, prompt, system):
    last_error = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            return _dispatch(provider, prompt, system)
        except Exception as e:
            last_error = e
            if attempt < MAX_RETRIES:
                wait = BACKOFF_SECONDS * (attempt + 1)
                print(f"[llm] {provider} attempt {attempt+1} failed: {e}. "
                      f"retrying in {wait}s...")
                time.sleep(wait)
    raise last_error     # all attempts failed


def _dispatch(provider, prompt, system):
    if provider == "ollama":
        return _call_ollama(prompt, system)
    if provider == "anthropic":
        return _call_anthropic(prompt, system)
    if provider == "bedrock":
        return _call_bedrock(prompt, system)
    raise ValueError(f"Unknown provider: {provider}")


def _record_cost(input_tokens, output_tokens):
    cost = (input_tokens / 1_000_000) * PRICE_INPUT_PER_M \
         + (output_tokens / 1_000_000) * PRICE_OUTPUT_PER_M
    LAST_USAGE["input_tokens"] = input_tokens
    LAST_USAGE["output_tokens"] = output_tokens
    LAST_USAGE["cost_usd"] = round(cost, 6)


# ============================================================
# OLLAMA  (free, local) — active
# ============================================================
def _call_ollama(prompt, system):
    from ollama import Client
    client = Client(timeout=TIMEOUT_SECONDS)          # timeout applied here
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    response = client.chat(model=OLLAMA_MODEL, messages=messages)
    _record_cost(0, 0)                                 # Ollama is free
    return response["message"]["content"]


# ============================================================
# ANTHROPIC  (Claude via API) — needs: pip install anthropic
# ============================================================
def _call_anthropic(prompt, system):
    import anthropic
    client = anthropic.Anthropic(
        api_key=os.environ["ANTHROPIC_API_KEY"],
        timeout=TIMEOUT_SECONDS,                        # timeout applied here
    )
    response = client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=1000,
        system=system,
        messages=[{"role": "user", "content": prompt}],
    )
    _record_cost(response.usage.input_tokens, response.usage.output_tokens)
    return response.content[0].text


# ============================================================
# BEDROCK  (Claude via AWS) — needs: pip install boto3 + AWS creds
# ============================================================
def _call_bedrock(prompt, system):
    import json
    import boto3
    from botocore.config import Config
    client = boto3.client(
        "bedrock-runtime",
        region_name="eu-west-2",
        config=Config(read_timeout=TIMEOUT_SECONDS),    # timeout applied here
    )
    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 1000,
        "system": system,
        "messages": [{"role": "user", "content": prompt}],
    }
    response = client.invoke_model(modelId=BEDROCK_MODEL, body=json.dumps(body))
    result = json.loads(response["body"].read())
    usage = result.get("usage", {})
    _record_cost(usage.get("input_tokens", 0), usage.get("output_tokens", 0))
    return result["content"][0]["text"]


# ============================================================
# QUICK TEST
# ============================================================
if __name__ == "__main__":
    answer = call_llm(
        prompt="Say 'hello, the wrapper works' and nothing else.",
        system="You are a test assistant. Reply briefly.",
    )
    print("LLM replied:", answer)
    print("Usage:", LAST_USAGE)
