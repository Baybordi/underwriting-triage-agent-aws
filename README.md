# SME Property Underwriting Triage Agent

> **Note:** This is a **simple first-stage prototype (PoC)** — a narrow, well-tested
> slice built to show the approach, not a finished product. Scope and tooling are
> kept deliberately small; production hardening is listed in *What I'd do next*.

An agentic AI prototype for **commercial/specialty underwriting**. It reads a
submission that comes in for **broker new-business support**, checks it against the
underwriting rules using retrieval-augmented generation (RAG), and recommends
**QUOTE / DECLINE / REFER** with a reason — for a human underwriter to approve or
override. The agent never makes the final decision.

> **Live demo (while the instance is running):** `http://16.60.164.25:8501`
> *(public IP; it changes if the EC2 instance is stopped/started.)*

---

## 1. How we found the business case

I looked at Intact Insurance UK's own operation — a commercial & specialty insurer
that works **through brokers** and is actively investing in **AI-assisted
underwriting**. On their site, the **broker support → new business** intake is where
submissions arrive and wait for a first-pass review. That queue is exactly where an
agent adds value: it triages each incoming support/new-business request in seconds,
so underwriters spend their time on judgement, not manual first-pass reading. The
use case is therefore grounded in Intact's real process, not a generic idea.

---

## 2. Business value

Underwriters spend hours manually triaging messy submissions, which slows quotes and
creates inconsistency. This agent does the first-pass triage automatically — extract
the risk, check appetite, recommend an action — speeding turnaround and improving
consistency, while keeping the human in control.

---

## 3. What it does (solution view)

**Step 1 — Offline (build once):**
synthetic rule docs → structural/heading chunking → embedding (`all-MiniLM-L6-v2`,
local, £0) → **FAISS** index (cosine) → persisted to **S3**.

**Step 2 — Runtime (per request):**
1. **Input protection** — Pydantic validation + guardrails (prompt-injection + harmful screen)
2. **Data protection** — PII masking before anything reaches the LLM
3. **RAG retrieval** — embed the query, cosine-search FAISS for the top-k rules
4. **LLM reasoning** — Claude applies **only the retrieved rules**
5. **Output protection** — Pydantic output schema + groundedness (cosine) guardrail.
   If groundedness is below threshold the answer is **regenerated (max 3 attempts)**;
   if it still can't reach a good cosine score, it **returns the answer anyway and
   shows the cosine rate** to the underwriter — it never crashes.
6. **Decision** — QUOTE / DECLINE / REFER (+ reason) → **human underwriter** approves/overrides
7. Fail-safe everywhere: on any error or low confidence → **REFER** (never crash, never guess)

Cross-cutting: logging (request id + source, hourly), audit (DynamoDB), metrics (CloudWatch).
See `solution_view.png`.

---

## 4. Platform (how it runs on AWS, eu-west-2)

| Service | Role |
|---|---|
| EC2 | Runs the Streamlit UI + agent |
| S3 | Stores the FAISS index + chunks (loaded at startup) |
| DynamoDB | Audit trail (one record per decision, correlated by request id) |
| CloudWatch | Logs + custom metrics + dashboard |
| IAM | Least-privilege role for the above |
| Anthropic API (primary) / Bedrock (fallback) | LLM |

See `platform_view.png & solution_view.png.

---

## 5. Evaluation results (offline, golden dataset)

A **12-case labelled golden dataset** (balanced QUOTE/DECLINE/REFER, including edge
and prompt-injection cases), measured in three separate layers:

| Layer | Metrics | Result |
|---|---|---|
| **Whole agent** | **Accuracy, Precision, Recall per class** | **~92–100% accuracy** (v2, Claude); DECLINE precision & recall = 1.0 |
| **LLM output** | Groundedness (cosine), hallucination rate | 0 hallucinations; groundedness ~0.77 |
| **RAG retrieval** | **Recall@k, Precision, MRR, cosine** | strict section-match ~42% — the honest next improvement |

This shows the agent already makes correct, grounded decisions on the test set, and
that the current bottleneck is **retrieval**, not reasoning — a data-driven finding,
not a guess.

---

## 6. Observability & metrics (per pipeline)

Every request emits **custom CloudWatch metrics**, timed **per stage**, so bottlenecks
are visible rather than guessed. A live dashboard shows:

| Metric | What it tells us |
|---|---|
| InputGuardLatency, **RetrievalLatency**, **LLMLatency**, OutputGuardLatency, TotalLatency | where time goes — the **LLM is the bottleneck** (~2s) vs retrieval (~60ms) |
| CostUSD, InputTokens, OutputTokens | cost per request |
| RequestCount (by decision & source), **ReferRate** | decision mix; how often it defers |
| GuardrailPassed, InjectionBlocked | safety working |
| **CosineGroundedness**, Groundedness | live hallucination signal |
| ErrorCount, LLMFallbackTriggered | reliability / resilience |
| Ingestion: ChunksIndexed, EmbeddingTimeMs | offline build health |

Logs are structured with a **request id + source (streamlit/terminal)** and split into
**hourly streams**, so any single run is traceable end-to-end across logs, the DynamoDB
audit record, and the metrics.

---

## 7. Risk, security & governance

- **Prompt injection** — screened at input; the agent ignores instructions hidden in submissions
- **PII** — masked before the LLM; secrets in `.env` (gitignored), never in code
- **Hallucination** — groundedness measured (cosine + word-overlap), low scores surfaced to the human
- **Fair treatment** — same rules applied to all; every decision logged with its reason
- **Auditability** — DynamoDB audit + CloudWatch logs, correlated by request id (FCA / EU AI Act traceability)
- **Human-on-the-loop** — the agent recommends; a person decides

---

## 8. How to run

**Local:**
```bash
python -m venv venv && source venv/bin/activate   # (Windows: venv\Scripts\activate)
pip install -r requirements.txt
# add your key to .env:  ANTHROPIC_API_KEY=sk-ant-...
python src/ingestion.py          # build the FAISS index (once)
streamlit run streamlit_app.py   # open http://localhost:8501
```
Switch LLM provider in `src/llm.py` (`PROVIDER = "ollama" | "anthropic" | "bedrock"`).
Ollama (`llama3.2`) was used for free local testing; Claude for the final run.

**AWS:** set `USE_S3=true`, `S3_BUCKET`, `USE_DYNAMODB=true`, `DYNAMO_TABLE`,
`USE_CLOUDWATCH_METRICS=true`, `AWS_DEFAULT_REGION=eu-west-2`, then run the same commands on EC2.

---

## 9. Key assumptions

- **Synthetic data only** — the 3 rule docs and 12 test cases are made up (no real/confidential data)
- Scope is **SME commercial property**; anything outside appetite → REFER
- FAISS (local/S3) chosen over a managed vector DB to keep PoC cost ~£0; MiniLM over Titan for £0 embeddings
- EC2 over containers for a single-instance PoC

---

## 10. What I'd do next (with more time)

- **Retrieval:** stronger embeddings + hybrid (keyword + vector) search and a reranker
- **Embeddings:** move to **Amazon Titan** on Bedrock (strong model, AWS-native)
- **LLM:** switch from the Anthropic API to **Amazon Bedrock**, so the data stays **inside AWS**
  and is not sent to an external service — a stronger security/compliance posture
- **Vector store:** a managed AWS vector database (e.g. OpenSearch) at scale — not used here to avoid cost
- **Security hardening:** **VPC isolation**, Secrets Manager, HTTPS, and **CloudFront** at the edge
- **Groundedness:** LLM-as-judge (Ragas/Langfuse) instead of a lexical/cosine proxy
- **Quality in production:** shadow mode → canary rollout; track **human-override rate** as the real accuracy signal
- **MLOps:** experiment/version tracking (MLflow/Langfuse), scheduled re-evaluation on each model/prompt change
- **Reuse:** expose retrieval + guardrail + audit as shared platform services so other teams build on the same paved road
