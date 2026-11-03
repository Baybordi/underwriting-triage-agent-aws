# Underwriting Triage Agent — Pipeline Blueprint

SME commercial property underwriting triage agent.
Reads a broker submission, extracts risk facts, checks underwriting appetite via RAG,
and recommends QUOTE / DECLINE / REFER (+ indicative price) for a human underwriter to approve.

---

## PIPELINE 0 — Resilience & Error Handling (wraps everything)
- 0.1 Try/except around every stage
- 0.2 Timeouts on all external calls (LLM, vector DB)
- 0.3 Retry with backoff on transient failures
- 0.4 Any unhandled error → REFER + log (never crash)
- 0.5 Log every error (stage, input, reason)

## PIPELINE 1 — Ingestion & Indexing (offline, run once)
- 1.1 Load the 3 knowledge docs
- 1.2 Chunk (structural — one rule/section per chunk)
- 1.3 Embed
- 1.4 Store in vector DB (Chroma local / OpenSearch prod)

## PIPELINE 2 — Input Protection (runtime)
- 2.1 Schema validation (Pydantic) — required fields, types, no nulls
- 2.2 Injection screen (guardrail) — strip hidden instructions
- 2.3 Size/format check
- 2.4 Fail-safe gate — invalid → REFER + log
- 2.5 Harmful content filter — screen input for abusive/harmful text

## PIPELINE 3 — Data Protection (runtime)
- 3.1 Detect & mask PII before LLM
- 3.2 Keep sensitive data in controlled store, not in prompts
- 3.3 Encrypt at rest + in transit (KMS)

## PIPELINE 4 — Agent Decision (core, runtime)
- 4.1 Extract risk facts → structured fields
- 4.2 Retrieve rules (RAG) — embed query → cosine similarity → top-k
- 4.3 Reason & decide → risk level + QUOTE/DECLINE/REFER
- 4.4 Price (if quote) → indicative range
- 4.5 Confidence gate — below threshold → retry; still low → REFER
- 4.6 LLM fallback — fail → retry/backoff → backup model → else REFER

## PIPELINE 5 — Caching (runtime)
- 5.1 Cache embeddings (no re-embedding same text)
- 5.2 Cache repeated query results
- 5.3 Cuts cost + latency

## PIPELINE 6 — Output Protection (runtime)
- 6.1 Schema enforce (Pydantic) — strict output JSON (decision, risk, reason, price)
- 6.2 Groundedness guardrail — business rules respected, no hallucination
- 6.3 Bad-output fallback — fails check → retry → REFER
- 6.4 Output + audit log — result + inputs + retrieved chunks + timing
- 6.5 Harmful content filter — ensure output is safe/professional

## PIPELINE 7 — Human-in-the-loop
- 7.1 Underwriter reviews recommendation
- 7.2 Approve / override (final decision = human)
- 7.3 Capture override → feeds improvement

## PIPELINE 8 — Versioning (governance)
- 8.1 Version the knowledge base
- 8.2 Version prompts
- 8.3 Version model — every decision traceable to exact versions

## PIPELINE 9 — Evaluation (golden dataset test loop)
- 9.1 Load golden dataset (the 12 labelled cases)
- 9.2 Run each case through the agent (feed submission → get output)
- 9.3 Compare vs ground truth (decision vs expected_decision; retrieved rule vs expected_relevant_rule)
- 9.4 Retrieval metrics: Recall@k, cosine
- 9.5 Decision metrics: accuracy (F1 / confusion matrix per category — later)
- 9.6 System metrics: latency, error rate, cost
- 9.7 Failure report: which cases failed, by category + difficulty (shows where it fails)

## PIPELINE 10 — Monitoring & Governance (production)
- 10.1 Live metrics (latency, error, cost, override rate, injection-blocked, REFER rate)
- 10.2 Drift watch
- 10.3 PoC → shadow mode → limited → full

---

## FLOW (inside Pipeline 0 wrapper)
Ingest → Input Protection → Data Protection → Agent Decision (+Caching)
→ Output Protection → Human Approval → (Versioning + Eval + Monitoring)

---

## GUARDRAILS SUMMARY (5, both sides)
- PII leakage — Pipeline 3 + 6.4
- Prompt injection — Pipeline 2.2
- Harmful content — Pipeline 2.5 + 6.5
- Business rule enforcement — Pipeline 6.2
- Output quality / schema — Pipeline 2.1 + 6.1
(In AWS: Bedrock Guardrails provides injection, PII and toxicity filters as a managed, reusable layer.)

---

## PARKING LOT — not built now, use later if needed
| # | Pipeline | Use later |
|---|----------|-----------|
| 1 | Feedback / retraining loop (overrides improve rules/prompts) | Production |
| 2 | Access control / auth (role-based) | Platform diagram (IAM) |
| 3 | Cost control / rate limiting (budget guard, throttle) | Scale |
| 4 | Notification / routing (REFER → right underwriter queue) | Production |

---

## KEY DECISIONS LOCKED IN
- Scope: SME commercial property only; anything outside → REFER
- Knowledge base: 3 separate docs (appetite guide, risk rules, pricing guidance)
- Golden dataset: 12 balanced labelled cases (4 QUOTE / 4 DECLINE / 4 REFER), with dual ground truth (decision + relevant rule), category + difficulty tags, incl. edge + injection cases. It is DATA used by Pipeline 9, not a pipeline itself.
- Chunking: structural (docs written to also support semantic/fixed)
- Retrieval similarity: cosine
- Vector DB: Chroma locally for PoC; OpenSearch as production target
- LLM: Anthropic API for local testing; Bedrock (same model family) for production
- LLM call kept behind one wrapper function → one-line swap to Bedrock
- Structure enforced by Pydantic, safety by guardrails — deterministic parts in code, AI only for the fuzzy parts
- Ultimate safety net everywhere: REFER to a human + log, never crash, never guess
