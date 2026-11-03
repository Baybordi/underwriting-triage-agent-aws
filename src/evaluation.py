"""
PIPELINE 9 — Evaluation (golden dataset test loop)

The evaluation is split into THREE CLEARLY SEPARATED LAYERS, each with its own
function so the code reads the same way the results do:

  LAYER 1 — eval_retrieval()   : did RAG extract the right rules?
  LAYER 2 — eval_llm_output()  : is the LLM answer valid / grounded / hallucinating?
  LAYER 3 — eval_system()      : accuracy, errors, latency per part

The main loop runs each case through the full pipeline, then calls the three
layer functions in order and collects their results.
"""

import json
import re
import time

from pipeline import run_pipeline
from version import get_version          # Pipeline 8 — version stamp

GOLDEN_FILE = "data/test_cases/golden_dataset.json"
RESULTS_FILE = "eval_results.jsonl"      # one evaluation run per line (history)
GROUNDEDNESS_THRESHOLD = 0.35   # below this -> possible hallucination


def load_golden():
    with open(GOLDEN_FILE, "r", encoding="utf-8") as f:
        return json.load(f)["cases"]


# ============================================================
# LAYER 1 — RAG RETRIEVAL
# "Did the agent fetch the correct rule section from the data?"
# ============================================================
def eval_retrieval(result, case):
    expected_rule = case["expected_relevant_rule"]
    want_src = expected_rule.split(" - ")[0].strip()          # file name
    m = re.search(r"Section\s+(\d+)", expected_rule)
    want_sec = m.group(1) if m else None

    # find the rank of the first retrieved chunk that matches file + section
    rank = 0
    for i, r in enumerate(result.get("rules_used", []), start=1):
        if r["source"] == want_src:
            sec_num = r["section"].split(".")[0].strip()
            if want_sec is None or sec_num == want_sec:
                rank = i
                break

    return {
        "hit": rank > 0,                               # was the right section found?
        "reciprocal_rank": (1.0 / rank) if rank else 0.0,   # for MRR
        "top_similarity": result.get("retrieval_similarity", 0),
        "rank": rank,
    }


# ============================================================
# LAYER 2 — LLM OUTPUT
# "Is the model's answer well-formed and grounded (not hallucinated)?"
# ============================================================
def _tokens(text):
    return set(re.findall(r"[a-z]{4,}", text.lower()))

def eval_llm_output(result):
    # groundedness: fraction of the reason's words that appear in retrieved rules
    reason_words = _tokens(result.get("reason", ""))
    retrieved_words = _tokens(" ".join(r["text"] for r in result.get("rules_used", [])))
    if reason_words:
        grounded = len(reason_words & retrieved_words) / len(reason_words)
    else:
        grounded = 0.0

    return {
        "schema_valid": bool(result.get("schema_valid")),
        "groundedness": grounded,
        "hallucinated": grounded < GROUNDEDNESS_THRESHOLD and result["stage"] == "agent",
    }


# ============================================================
# LAYER 3 — WHOLE AGENT
# "Is the final decision correct? Any errors? How fast is each part?"
# ============================================================
def eval_system(result, case):
    return {
        "correct": result["decision"] == case["expected_decision"],
        "error": result["stage"] == "error",
        "retrieval_ms": result.get("retrieval_ms", 0),
        "llm_ms": result.get("llm_ms", 0),
    }


# ============================================================
# MAIN LOOP — run each case, then call the 3 layer functions
# ============================================================
def run_evaluation():
    cases = load_golden()
    total = len(cases)

    # layer 1 collectors
    recall_hits = 0
    reciprocal_ranks = []
    top_sims = []
    # layer 2 collectors
    schema_valid = 0
    groundedness_scores = []
    hallucinations = []
    # layer 3 collectors
    correct = 0
    errors = 0
    retrieval_times = []
    llm_times = []
    # per-class + failures
    labels = ["QUOTE", "DECLINE", "REFER"]
    tp = {l: 0 for l in labels}; fp = {l: 0 for l in labels}; fn = {l: 0 for l in labels}
    failures = []

    print(f"Running {total} golden cases...\n")

    for case in cases:
        result = run_pipeline(case["submission"])

        # ---- run the three evaluation layers ----
        L1 = eval_retrieval(result, case)
        L2 = eval_llm_output(result)
        L3 = eval_system(result, case)

        # collect layer 1
        if L1["hit"]:
            recall_hits += 1
        reciprocal_ranks.append(L1["reciprocal_rank"])
        top_sims.append(L1["top_similarity"])
        # collect layer 2
        if L2["schema_valid"]:
            schema_valid += 1
        groundedness_scores.append(L2["groundedness"])
        if L2["hallucinated"]:
            hallucinations.append(case["id"])
        # collect layer 3
        if L3["correct"]:
            correct += 1
        if L3["error"]:
            errors += 1
        retrieval_times.append(L3["retrieval_ms"])
        llm_times.append(L3["llm_ms"])

        # per-class tallies
        exp, act = case["expected_decision"], result["decision"]
        if act == exp and act in tp:
            tp[act] += 1
        else:
            if act in fp: fp[act] += 1
            if exp in fn: fn[exp] += 1

        if not L3["correct"]:
            failures.append((case["id"], case["category"], case["difficulty"],
                             exp, act, result["reason"]))

        mark = "OK " if L3["correct"] else "XX "
        print(f"{mark}{case['id']} [{case['category']}/{case['difficulty']}] "
              f"exp={exp} got={act} | rank={L1['rank']} ground={L2['groundedness']:.2f} "
              f"| ret={L3['retrieval_ms']}ms llm={L3['llm_ms']}ms")

    # ---------------- REPORTS ----------------
    print("\n" + "=" * 60)
    print("LAYER 1 — RAG RETRIEVAL (did it extract the right rules?)")
    print("=" * 60)
    print(f"Recall@k (correct section retrieved): {recall_hits}/{total} ({recall_hits/total*100:.0f}%)")
    print(f"MRR (rank quality, 1.0 = always top): {sum(reciprocal_ranks)/total:.2f}")
    print(f"Avg top similarity                  : {sum(top_sims)/total:.2f}")

    print("\n" + "=" * 60)
    print("LAYER 2 — LLM OUTPUT (is the answer ok / hallucinating?)")
    print("=" * 60)
    print(f"Schema-valid rate : {schema_valid}/{total} ({schema_valid/total*100:.0f}%)")
    print(f"Avg groundedness  : {sum(groundedness_scores)/total:.2f} (1.0 = fully grounded)")
    print(f"Possible hallucinations: {len(hallucinations)} {hallucinations}")

    print("\n" + "=" * 60)
    print("LAYER 3 — WHOLE AGENT (accuracy, errors, latency)")
    print("=" * 60)
    print(f"Decision accuracy : {correct}/{total} ({correct/total*100:.0f}%)")
    print(f"Errors            : {errors}")
    print(f"Avg retrieval time: {sum(retrieval_times)/total:.0f} ms")
    print(f"Avg LLM time      : {sum(llm_times)/total:.0f} ms")

    print("\nPer-class precision / recall / F1:")
    print(f"  {'class':8s}  {'prec':>5s}  {'rec':>5s}  {'f1':>5s}")
    for l in labels:
        prec = tp[l] / (tp[l] + fp[l]) if (tp[l] + fp[l]) else 0
        rec = tp[l] / (tp[l] + fn[l]) if (tp[l] + fn[l]) else 0
        f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0
        print(f"  {l:8s}  {prec:5.2f}  {rec:5.2f}  {f1:5.2f}")

    if failures:
        print("\nFAILURES (where it fails):")
        for fid, cat, diff, exp, act, reason in failures:
            print(f"  {fid} [{cat}/{diff}] expected {exp}, got {act}")
            print(f"      reason: {reason}")
    else:
        print("\nNo failures.")

    # ============================================================
    # PIPELINE 8 — save this run's results, stamped with the version
    # (lets you compare runs later: v1 vs v2 accuracy, etc.)
    # ============================================================
    summary = {
        "time": time.strftime("%Y-%m-%d %H:%M:%S"),
        "version": get_version(),
        "retrieval": {
            "recall_at_k": round(recall_hits / total, 3),
            "mrr": round(sum(reciprocal_ranks) / total, 3),
            "avg_top_similarity": round(sum(top_sims) / total, 3),
        },
        "llm_output": {
            "schema_valid_rate": round(schema_valid / total, 3),
            "avg_groundedness": round(sum(groundedness_scores) / total, 3),
            "hallucinations": len(hallucinations),
        },
        "system": {
            "accuracy": round(correct / total, 3),
            "errors": errors,
            "avg_retrieval_ms": round(sum(retrieval_times) / total),
            "avg_llm_ms": round(sum(llm_times) / total),
        },
    }
    with open(RESULTS_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(summary) + "\n")
    print(f"\nResults saved to {RESULTS_FILE} "
          f"(version {summary['version']['config_version']}, accuracy {summary['system']['accuracy']})")


if __name__ == "__main__":
    run_evaluation()
