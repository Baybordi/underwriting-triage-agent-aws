"""
PIPELINE 1 — Ingestion & Indexing (offline, run once)

Loads the 3 knowledge-base documents, splits them into chunks, creates embeddings,
and stores them using FAISS (a fast, stable local vector index).

Why FAISS (not Chroma)? FAISS is a lightweight, rock-solid vector-search library
with no database engine behind it — ideal for a local PoC on Windows.

We save two files in data/vector_store/:
  - index.faiss  : the vector index (for cosine similarity search)
  - chunks.json  : the chunk texts + metadata (so we can show what was retrieved)

Two chunking strategies are provided so they can be compared:
  - "heading"  : split by "## " section headings  (best for our structured rule docs)
  - "semantic" : group sentences by meaning        (better for unstructured text)

Run once before using the agent.
"""

import os
import re
import json
import numpy as np
import faiss
from sentence_transformers import SentenceTransformer

# ============================================================
# SETTINGS
# ============================================================
KB_FOLDER = "data/knowledge_base"
DB_FOLDER = "data/vector_store"
INDEX_FILE = os.path.join(DB_FOLDER, "index.faiss")
CHUNKS_FILE = os.path.join(DB_FOLDER, "chunks.json")
EMBED_MODEL = "all-MiniLM-L6-v2"

CHUNK_STRATEGY = "heading"        # "heading" or "semantic"
SEMANTIC_THRESHOLD = 0.6


# ============================================================
# METADATA HELPER
# ============================================================
def doc_type_from_filename(filename):
    if "appetite" in filename:
        return "appetite"
    if "risk" in filename:
        return "rules"
    if "pricing" in filename:
        return "pricing"
    return "other"


# ============================================================
# CHUNKING STRATEGY 1 — HEADING-BASED (structural)
# ============================================================
def chunk_by_heading(text, filename):
    chunks = []
    for section in text.split("## "):
        section = section.strip()
        if not section:
            continue
        section_title = section.split("\n")[0].strip()
        chunks.append({
            "text": section,
            "source": filename,
            "doc_type": doc_type_from_filename(filename),
            "section": section_title,
        })
    return chunks


# ============================================================
# CHUNKING STRATEGY 2 — SEMANTIC (group similar sentences)
# ============================================================
def chunk_semantic(text, filename, model):
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
    if not sentences:
        return []
    embs = model.encode(sentences)
    chunks, current = [], [sentences[0]]
    for i in range(1, len(sentences)):
        a, b = embs[i], embs[i - 1]
        sim = np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))
        if sim >= SEMANTIC_THRESHOLD:
            current.append(sentences[i])
        else:
            chunks.append(" ".join(current))
            current = [sentences[i]]
    chunks.append(" ".join(current))
    return [{
        "text": c,
        "source": filename,
        "doc_type": doc_type_from_filename(filename),
        "section": "semantic",
    } for c in chunks]


# ============================================================
# LOAD + CHUNK ALL DOCUMENTS
# ============================================================
def load_and_chunk(folder, strategy, model=None):
    chunks = []
    for filename in os.listdir(folder):
        if not filename.endswith(".md"):
            continue
        with open(os.path.join(folder, filename), "r", encoding="utf-8") as f:
            text = f.read()
        if strategy == "heading":
            chunks.extend(chunk_by_heading(text, filename))
        elif strategy == "semantic":
            chunks.extend(chunk_semantic(text, filename, model))
        else:
            raise ValueError(f"Unknown chunk strategy: {strategy}")
    return chunks


# ============================================================
# BUILD THE INDEX
# ============================================================
def build_index():
    os.makedirs(DB_FOLDER, exist_ok=True)

    print("Loading embedding model...")
    model = SentenceTransformer(EMBED_MODEL)

    print(f"Chunking documents using '{CHUNK_STRATEGY}' strategy...")
    chunks = load_and_chunk(KB_FOLDER, CHUNK_STRATEGY, model)
    print(f"Created {len(chunks)} chunks.\n")

    # ---- Show each chunk with metadata ----
    print("=" * 60)
    print("CHUNK PREVIEW (text + metadata)")
    print("=" * 60)
    for i, c in enumerate(chunks):
        print(f"\n----- CHUNK {i + 1} -----")
        print(f"  source   : {c['source']}")
        print(f"  doc_type : {c['doc_type']}")
        print(f"  section  : {c['section']}")
        print(f"  text     : {c['text'][:200]}...")
    print("\n" + "=" * 60 + "\n")

    print("Creating embeddings...")
    texts = [c["text"] for c in chunks]
    embeddings = model.encode(texts)
    embeddings = np.array(embeddings, dtype="float32")

    # Normalise so that inner-product search == cosine similarity
    faiss.normalize_L2(embeddings)

    print("Building FAISS index...")
    dim = embeddings.shape[1]
    index = faiss.IndexFlatIP(dim)   # inner product on normalised vectors = cosine
    index.add(embeddings)

    print("Saving index and chunks...")
    faiss.write_index(index, INDEX_FILE)
    with open(CHUNKS_FILE, "w", encoding="utf-8") as f:
        json.dump(chunks, f, indent=2)

    print(f"Done. Indexed {len(chunks)} chunks.")
    print(f"  - {INDEX_FILE}")
    print(f"  - {CHUNKS_FILE}")

    # ---- Prove metadata is stored: show chunk 0 ----
    print("\nVerifying stored chunk 0:")
    print(json.dumps(chunks[0], indent=2))


if __name__ == "__main__":
    build_index()
