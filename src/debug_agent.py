"""
TEMPORARY DEBUG VERSION — run this to see exactly where the agent stops.
Put it in src/ next to agent.py, run: python src/debug_agent.py
Delete it once we know the problem.
"""

print("STEP 0: script started")

import json
import chromadb
from sentence_transformers import SentenceTransformer
from llm import call_llm

print("STEP 1: imports ok")

DB_FOLDER = "data/vector_store"
COLLECTION_NAME = "underwriting_rules"
EMBED_MODEL = "all-MiniLM-L6-v2"

model = SentenceTransformer(EMBED_MODEL)
print("STEP 2: embedding model loaded")

client = chromadb.PersistentClient(path=DB_FOLDER)
collection = client.get_collection(COLLECTION_NAME)
print("STEP 3: connected to Chroma, count =", collection.count())

submission = ("Business: Marketing agency office, Manchester. Sum insured 800000. "
              "Built 2005. No claims in 5 years. Smoke alarms fitted.")

q = model.encode(submission).tolist()
results = collection.query(query_embeddings=[q], n_results=4,
                           include=["documents", "metadatas", "distances"])
print("STEP 4: retrieval ok, got", len(results["documents"][0]), "chunks")
for doc, dist in zip(results["documents"][0], results["distances"][0]):
    print(f"   sim={round(1-dist,3)}  {doc[:50]}...")

print("STEP 5: calling the LLM (this may take 20-40s)...")
rules_text = "\n".join(results["documents"][0])
prompt = f"RULES:\n{rules_text}\n\nSUBMISSION:\n{submission}\n\nReply with JSON: decision, risk_level, reason, confidence."
raw = call_llm(prompt, system="You are an underwriting triage assistant. Reply only JSON.")
print("STEP 6: LLM replied. RAW OUTPUT BELOW:")
print("-" * 50)
print(raw)
print("-" * 50)
