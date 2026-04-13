"""
rag_answer.py — Sprint 2 + Sprint 3: Retrieval & Grounded Answer
================================================================
Sprint 2: Dense retrieval + grounded answer với citation
Sprint 3: Hybrid retrieval (dense + BM25) với Reciprocal Rank Fusion
"""

import os
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv

load_dotenv()

# Disable TensorFlow to avoid Keras 3 / torchvision conflicts in this environment
os.environ.setdefault("USE_TF", "0")
os.environ.setdefault("USE_TORCH", "1")

# =============================================================================
# CẤU HÌNH
# =============================================================================

TOP_K_SEARCH = 10
TOP_K_SELECT = 3

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")


# =============================================================================
# RETRIEVAL — DENSE (Vector Search)
# =============================================================================

def retrieve_dense(query: str, top_k: int = TOP_K_SEARCH) -> List[Dict[str, Any]]:
    """Dense retrieval: tìm kiếm theo embedding similarity trong ChromaDB."""
    import chromadb
    from index import get_embedding, CHROMA_DB_DIR

    client = chromadb.PersistentClient(path=str(CHROMA_DB_DIR))
    collection = client.get_collection("rag_lab")

    query_embedding = get_embedding(query)
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=min(top_k, collection.count()),
        include=["documents", "metadatas", "distances"]
    )

    chunks = []
    for doc, meta, dist in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        chunks.append({
            "text": doc,
            "metadata": meta,
            "score": 1.0 - dist,  # cosine distance → similarity
        })

    return chunks


# =============================================================================
# RETRIEVAL — SPARSE / BM25 (Keyword Search)
# =============================================================================

# Cache BM25 index
_bm25_index = None
_bm25_chunks = None

def _build_bm25_index():
    """Build BM25 index từ tất cả chunks trong ChromaDB."""
    global _bm25_index, _bm25_chunks
    if _bm25_index is not None:
        return _bm25_index, _bm25_chunks

    from rank_bm25 import BM25Okapi
    import chromadb
    from index import CHROMA_DB_DIR

    client = chromadb.PersistentClient(path=str(CHROMA_DB_DIR))
    collection = client.get_collection("rag_lab")
    results = collection.get(include=["documents", "metadatas"])

    _bm25_chunks = []
    for doc, meta in zip(results["documents"], results["metadatas"]):
        _bm25_chunks.append({"text": doc, "metadata": meta})

    tokenized_corpus = [chunk["text"].lower().split() for chunk in _bm25_chunks]
    _bm25_index = BM25Okapi(tokenized_corpus)
    return _bm25_index, _bm25_chunks


def retrieve_sparse(query: str, top_k: int = TOP_K_SEARCH) -> List[Dict[str, Any]]:
    """Sparse retrieval: tìm kiếm theo keyword (BM25). Không cần sentence-transformers."""
    bm25, all_chunks = _build_bm25_index()
    tokenized_query = query.lower().split()
    scores = bm25.get_scores(tokenized_query)

    top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]

    results = []
    for idx in top_indices:
        results.append({
            "text": all_chunks[idx]["text"],
            "metadata": all_chunks[idx]["metadata"],
            "score": float(scores[idx]),
        })
    return results


# =============================================================================
# RETRIEVAL — HYBRID (Dense + Sparse với Reciprocal Rank Fusion)
# =============================================================================

def retrieve_hybrid(
    query: str,
    top_k: int = TOP_K_SEARCH,
    dense_weight: float = 0.6,
    sparse_weight: float = 0.4,
) -> List[Dict[str, Any]]:
    """
    Hybrid retrieval: kết hợp dense và sparse bằng Reciprocal Rank Fusion (RRF).
    RRF_score(doc) = dense_weight * 1/(60+rank_dense) + sparse_weight * 1/(60+rank_sparse)
    """
    dense_results = retrieve_dense(query, top_k=top_k)
    sparse_results = retrieve_sparse(query, top_k=top_k)

    # Tạo map từ chunk text → RRF score
    rrf_scores: Dict[str, float] = {}
    chunk_map: Dict[str, Dict] = {}

    for rank, chunk in enumerate(dense_results):
        key = chunk["text"][:100]  # dùng 100 ký tự đầu làm key
        rrf_scores[key] = rrf_scores.get(key, 0) + dense_weight * (1.0 / (60 + rank))
        chunk_map[key] = chunk

    for rank, chunk in enumerate(sparse_results):
        key = chunk["text"][:100]
        rrf_scores[key] = rrf_scores.get(key, 0) + sparse_weight * (1.0 / (60 + rank))
        if key not in chunk_map:
            chunk_map[key] = chunk

    # Sort theo RRF score
    sorted_keys = sorted(rrf_scores.keys(), key=lambda k: rrf_scores[k], reverse=True)

    results = []
    for key in sorted_keys[:top_k]:
        chunk = chunk_map[key].copy()
        chunk["score"] = rrf_scores[key]
        results.append(chunk)

    return results


# =============================================================================
# RERANK (Sprint 3 — cross-encoder)
# =============================================================================

_rerank_model = None

def rerank(
    query: str,
    candidates: List[Dict[str, Any]],
    top_k: int = TOP_K_SELECT,
) -> List[Dict[str, Any]]:
    """Rerank các candidate chunks bằng cross-encoder."""
    global _rerank_model
    if not candidates:
        return candidates

    try:
        from sentence_transformers import CrossEncoder
        if _rerank_model is None:
            _rerank_model = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")

        pairs = [[query, chunk["text"]] for chunk in candidates]
        scores = _rerank_model.predict(pairs)
        ranked = sorted(zip(candidates, scores), key=lambda x: x[1], reverse=True)
        return [chunk for chunk, _ in ranked[:top_k]]
    except Exception:
        # Fallback nếu cross-encoder không available
        return candidates[:top_k]


# =============================================================================
# QUERY TRANSFORMATION
# =============================================================================

def transform_query(query: str, strategy: str = "expansion") -> List[str]:
    """Biến đổi query để tăng recall."""
    try:
        prompt = f"""Given the query: '{query}'
Generate 2-3 alternative phrasings or related terms in Vietnamese that could help find relevant documents.
Output as a JSON array of strings only, no explanation.
Example: ["phiên bản khác của câu hỏi", "từ khóa liên quan"]"""

        answer = call_llm(prompt)
        import json
        # Tìm JSON array trong response
        match = __import__("re").search(r'\[.*?\]', answer, __import__("re").DOTALL)
        if match:
            alternatives = json.loads(match.group())
            return [query] + alternatives
    except Exception:
        pass
    return [query]


# =============================================================================
# GENERATION — GROUNDED ANSWER FUNCTION
# =============================================================================

def build_context_block(chunks: List[Dict[str, Any]]) -> str:
    """Đóng gói danh sách chunks thành context block để đưa vào prompt."""
    context_parts = []
    for i, chunk in enumerate(chunks, 1):
        meta = chunk.get("metadata", {})
        source = meta.get("source", "unknown")
        section = meta.get("section", "")
        score = chunk.get("score", 0)
        text = chunk.get("text", "")

        header = f"[{i}] {source}"
        if section:
            header += f" | {section}"
        if score > 0:
            header += f" | score={score:.3f}"

        context_parts.append(f"{header}\n{text}")

    return "\n\n".join(context_parts)


def build_grounded_prompt(query: str, context_block: str) -> str:
    """
    Grounded prompt theo 4 quy tắc:
    1. Evidence-only: Chỉ trả lời từ retrieved context
    2. Abstain: Thiếu context thì nói không đủ dữ liệu
    3. Citation: Gắn source/section khi có thể
    4. Short, clear, stable
    """
    prompt = f"""Answer only from the retrieved context below.
If the context is insufficient to answer the question, explicitly state that the information is not available in the provided documents. Do not make up information.
Cite the source field (in brackets like [1]) when possible.
Keep your answer short, clear, and factual.
Respond in the same language as the question.

Question: {query}

Context:
{context_block}

Answer:"""
    return prompt


def call_llm(prompt: str) -> str:
    """Gọi LLM để sinh câu trả lời."""
    if LLM_PROVIDER == "gemini":
        import google.generativeai as genai
        genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
        model = genai.GenerativeModel("gemini-1.5-flash")
        response = model.generate_content(
            prompt,
            generation_config={"temperature": 0, "max_output_tokens": 512}
        )
        return response.text
    else:
        # Default: OpenAI
        from openai import OpenAI
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        response = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=512,
        )
        return response.choices[0].message.content


def rag_answer(
    query: str,
    retrieval_mode: str = "dense",
    top_k_search: int = TOP_K_SEARCH,
    top_k_select: int = TOP_K_SELECT,
    use_rerank: bool = False,
    verbose: bool = False,
) -> Dict[str, Any]:
    """
    Pipeline RAG hoàn chỉnh: query → retrieve → (rerank) → generate.

    Returns:
        Dict với answer, sources, chunks_used, query, config
    """
    config = {
        "retrieval_mode": retrieval_mode,
        "top_k_search": top_k_search,
        "top_k_select": top_k_select,
        "use_rerank": use_rerank,
    }

    # --- Bước 1: Retrieve ---
    if retrieval_mode == "dense":
        candidates = retrieve_dense(query, top_k=top_k_search)
    elif retrieval_mode == "sparse":
        candidates = retrieve_sparse(query, top_k=top_k_search)
    elif retrieval_mode == "hybrid":
        candidates = retrieve_hybrid(query, top_k=top_k_search)
    else:
        raise ValueError(f"retrieval_mode không hợp lệ: {retrieval_mode}")

    if verbose:
        print(f"\n[RAG] Query: {query}")
        print(f"[RAG] Retrieved {len(candidates)} candidates (mode={retrieval_mode})")
        for i, c in enumerate(candidates[:3]):
            print(f"  [{i+1}] score={c.get('score', 0):.3f} | {c['metadata'].get('source', '?')}")

    # --- Bước 2: Rerank hoặc truncate ---
    if use_rerank:
        candidates = rerank(query, candidates, top_k=top_k_select)
    else:
        candidates = candidates[:top_k_select]

    if verbose:
        print(f"[RAG] After select: {len(candidates)} chunks")

    # --- Bước 3: Build context và prompt ---
    context_block = build_context_block(candidates)
    prompt = build_grounded_prompt(query, context_block)

    if verbose:
        print(f"\n[RAG] Prompt (first 500 chars):\n{prompt[:500]}...\n")

    # --- Bước 4: Generate ---
    answer = call_llm(prompt)

    # --- Bước 5: Extract sources ---
    sources = list({
        c["metadata"].get("source", "unknown")
        for c in candidates
    })

    return {
        "query": query,
        "answer": answer,
        "sources": sources,
        "chunks_used": candidates,
        "config": config,
    }


# =============================================================================
# SPRINT 3: SO SÁNH BASELINE VS VARIANT
# =============================================================================

def compare_retrieval_strategies(query: str) -> None:
    """So sánh các retrieval strategies với cùng một query."""
    print(f"\n{'='*60}")
    print(f"Query: {query}")
    print('='*60)

    strategies = [
        ("dense", False),
        ("hybrid", False),
        ("hybrid", True),
    ]

    for strategy, use_rerank in strategies:
        label = f"{strategy}" + (" + rerank" if use_rerank else "")
        print(f"\n--- Strategy: {label} ---")
        try:
            result = rag_answer(query, retrieval_mode=strategy, use_rerank=use_rerank, verbose=False)
            print(f"Answer: {result['answer'][:200]}")
            print(f"Sources: {result['sources']}")
        except Exception as e:
            print(f"Lỗi: {e}")


# =============================================================================
# MAIN — Demo và Test
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("Sprint 2 + 3: RAG Answer Pipeline")
    print("=" * 60)

    test_queries = [
        "SLA xử lý ticket P1 là bao lâu?",
        "Khách hàng có thể yêu cầu hoàn tiền trong bao nhiêu ngày?",
        "Ai phải phê duyệt để cấp quyền Level 3?",
        "ERR-403-AUTH là lỗi gì?",  # Abstain test
    ]

    print("\n--- Sprint 2: Test Baseline (Dense) ---")
    for query in test_queries:
        print(f"\nQuery: {query}")
        try:
            result = rag_answer(query, retrieval_mode="dense", verbose=True)
            print(f"Answer: {result['answer']}")
            print(f"Sources: {result['sources']}")
        except Exception as e:
            print(f"Lỗi: {e}")

    print("\n--- Sprint 3: So sánh strategies ---")
    compare_retrieval_strategies("Approval Matrix để cấp quyền là tài liệu nào?")
    compare_retrieval_strategies("ERR-403-AUTH")
