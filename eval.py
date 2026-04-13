"""
eval.py — Sprint 4: Evaluation & Scorecard
==========================================
Chạy 10 test questions, chấm điểm 4 metrics, so sánh baseline vs variant.
Hỗ trợ LLM-as-Judge (bonus) và chấm thủ công.
"""

import json
import csv
import os
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
from rag_answer import rag_answer, call_llm

# =============================================================================
# CẤU HÌNH
# =============================================================================

TEST_QUESTIONS_PATH = Path(__file__).parent / "data" / "test_questions.json"
RESULTS_DIR = Path(__file__).parent / "results"
LOGS_DIR = Path(__file__).parent / "logs"

BASELINE_CONFIG = {
    "retrieval_mode": "dense",
    "top_k_search": 10,
    "top_k_select": 3,
    "use_rerank": False,
    "label": "baseline_dense",
}

VARIANT_CONFIG = {
    "retrieval_mode": "hybrid",
    "top_k_search": 10,
    "top_k_select": 3,
    "use_rerank": False,
    "label": "variant_hybrid",
}

# Dùng LLM-as-Judge nếu có API key (bonus +2)
USE_LLM_JUDGE = True


# =============================================================================
# SCORING FUNCTIONS — LLM-as-Judge
# =============================================================================

def _llm_judge(prompt: str, default_score: int = 3) -> Dict[str, Any]:
    """Gọi LLM để chấm điểm, trả về score và reason."""
    try:
        response = call_llm(prompt)
        # Parse JSON từ response
        import re
        match = re.search(r'\{.*?\}', response, re.DOTALL)
        if match:
            data = json.loads(match.group())
            return {
                "score": int(data.get("score", default_score)),
                "notes": data.get("reason", data.get("notes", "")),
            }
    except Exception as e:
        pass
    return {"score": default_score, "notes": "LLM judge parse error — default score"}


def score_faithfulness(
    answer: str,
    chunks_used: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Faithfulness: Câu trả lời có bám đúng chứng cứ đã retrieve không?
    Thang điểm 1-5.
    """
    if not answer or answer.startswith("PIPELINE"):
        return {"score": 1, "notes": "Pipeline error"}

    if not chunks_used:
        return {"score": 1, "notes": "No chunks retrieved"}

    if USE_LLM_JUDGE:
        context_preview = "\n".join([c["text"][:200] for c in chunks_used[:3]])
        prompt = f"""You are an evaluation judge for a RAG system.

Retrieved context:
{context_preview}

Model answer:
{answer}

Rate the FAITHFULNESS of the answer on a scale of 1-5:
5 = Every claim in the answer is directly supported by the retrieved context
4 = Almost entirely grounded, one minor uncertain detail
3 = Mostly grounded, some info may come from model knowledge
2 = Several claims not found in retrieved context
1 = Answer is mostly hallucinated / not grounded

Output ONLY valid JSON: {{"score": <int 1-5>, "reason": "<one sentence>"}}"""
        return _llm_judge(prompt, default_score=3)

    # Fallback: heuristic — nếu answer có "không có thông tin" → faithful abstain
    abstain_phrases = ["không có thông tin", "không đủ dữ liệu", "không tìm thấy", "i don't know", "not available"]
    if any(p in answer.lower() for p in abstain_phrases):
        return {"score": 5, "notes": "Correct abstain — faithful to context"}

    return {"score": 3, "notes": "Manual review needed"}


def score_answer_relevance(
    query: str,
    answer: str,
) -> Dict[str, Any]:
    """Answer Relevance: Answer có trả lời đúng câu hỏi không? Thang 1-5."""
    if not answer or answer.startswith("PIPELINE"):
        return {"score": 1, "notes": "Pipeline error"}

    if USE_LLM_JUDGE:
        prompt = f"""You are an evaluation judge for a RAG system.

Question: {query}

Answer: {answer}

Rate the ANSWER RELEVANCE on a scale of 1-5:
5 = Answer directly and completely addresses the question
4 = Answers correctly but missing minor details
3 = Partially relevant but not fully on-topic
2 = Mostly off-topic
1 = Does not answer the question at all

Output ONLY valid JSON: {{"score": <int 1-5>, "reason": "<one sentence>"}}"""
        return _llm_judge(prompt, default_score=3)

    return {"score": 3, "notes": "Manual review needed"}


def score_context_recall(
    chunks_used: List[Dict[str, Any]],
    expected_sources: List[str],
) -> Dict[str, Any]:
    """Context Recall: Retriever có mang về đủ evidence cần thiết không?"""
    if not expected_sources:
        return {"score": 5, "recall": 1.0, "notes": "No expected sources (abstain case) — full score"}

    retrieved_sources = {
        c.get("metadata", {}).get("source", "")
        for c in chunks_used
    }

    found = 0
    missing = []
    for expected in expected_sources:
        expected_name = expected.split("/")[-1].replace(".pdf", "").replace(".md", "")
        matched = any(expected_name.lower() in r.lower() for r in retrieved_sources)
        if matched:
            found += 1
        else:
            missing.append(expected)

    recall = found / len(expected_sources) if expected_sources else 0
    score = max(1, round(recall * 5))

    return {
        "score": score,
        "recall": recall,
        "found": found,
        "missing": missing,
        "notes": f"Retrieved: {found}/{len(expected_sources)} expected sources" +
                 (f". Missing: {missing}" if missing else ""),
    }


def score_completeness(
    query: str,
    answer: str,
    expected_answer: str,
) -> Dict[str, Any]:
    """Completeness: Answer có bao phủ đủ thông tin so với expected_answer không?"""
    if not answer or answer.startswith("PIPELINE"):
        return {"score": 1, "notes": "Pipeline error"}

    if not expected_answer:
        return {"score": None, "notes": "No expected answer provided"}

    if USE_LLM_JUDGE:
        prompt = f"""You are an evaluation judge for a RAG system.

Question: {query}

Expected answer (reference): {expected_answer}

Model answer: {answer}

Rate the COMPLETENESS on a scale of 1-5:
5 = Model answer covers all key points from the expected answer
4 = Missing one minor detail
3 = Missing some important information
2 = Missing most important information
1 = Missing almost all key content

Output ONLY valid JSON: {{"score": <int 1-5>, "reason": "<one sentence>"}}"""
        return _llm_judge(prompt, default_score=3)

    return {"score": 3, "notes": "Manual review needed"}


# =============================================================================
# SCORECARD RUNNER
# =============================================================================

def run_scorecard(
    config: Dict[str, Any],
    test_questions: Optional[List[Dict]] = None,
    verbose: bool = True,
) -> List[Dict[str, Any]]:
    """Chạy toàn bộ test questions qua pipeline và chấm điểm."""
    if test_questions is None:
        with open(TEST_QUESTIONS_PATH, "r", encoding="utf-8") as f:
            test_questions = json.load(f)

    results = []
    label = config.get("label", "unnamed")

    print(f"\n{'='*70}")
    print(f"Chạy scorecard: {label}")
    print(f"Config: {config}")
    print('='*70)

    for q in test_questions:
        question_id = q["id"]
        query = q["question"]
        expected_answer = q.get("expected_answer", "")
        expected_sources = q.get("expected_sources", [])
        category = q.get("category", "")

        if verbose:
            print(f"\n[{question_id}] {query}")

        try:
            result = rag_answer(
                query=query,
                retrieval_mode=config.get("retrieval_mode", "dense"),
                top_k_search=config.get("top_k_search", 10),
                top_k_select=config.get("top_k_select", 3),
                use_rerank=config.get("use_rerank", False),
                verbose=False,
            )
            answer = result["answer"]
            chunks_used = result["chunks_used"]

        except Exception as e:
            answer = f"PIPELINE_ERROR: {e}"
            chunks_used = []

        # Chấm điểm
        faith = score_faithfulness(answer, chunks_used)
        relevance = score_answer_relevance(query, answer)
        recall = score_context_recall(chunks_used, expected_sources)
        complete = score_completeness(query, answer, expected_answer)

        row = {
            "id": question_id,
            "category": category,
            "query": query,
            "answer": answer,
            "expected_answer": expected_answer,
            "faithfulness": faith["score"],
            "faithfulness_notes": faith.get("notes", ""),
            "relevance": relevance["score"],
            "relevance_notes": relevance.get("notes", ""),
            "context_recall": recall["score"],
            "context_recall_notes": recall.get("notes", ""),
            "completeness": complete["score"],
            "completeness_notes": complete.get("notes", ""),
            "config_label": label,
        }
        results.append(row)

        if verbose:
            print(f"  Answer: {answer[:120]}...")
            print(f"  Faithful: {faith['score']} | Relevant: {relevance['score']} | "
                  f"Recall: {recall['score']} | Complete: {complete['score']}")

    # Tính averages
    metrics = ["faithfulness", "relevance", "context_recall", "completeness"]
    print(f"\n--- Average Scores ({label}) ---")
    for metric in metrics:
        scores = [r[metric] for r in results if r[metric] is not None]
        avg = sum(scores) / len(scores) if scores else None
        print(f"  {metric}: {avg:.2f}/5" if avg else f"  {metric}: N/A")

    return results


# =============================================================================
# A/B COMPARISON
# =============================================================================

def compare_ab(
    baseline_results: List[Dict],
    variant_results: List[Dict],
    output_csv: Optional[str] = None,
) -> None:
    """So sánh baseline vs variant theo từng câu hỏi và tổng thể."""
    metrics = ["faithfulness", "relevance", "context_recall", "completeness"]

    print(f"\n{'='*70}")
    print("A/B Comparison: Baseline vs Variant")
    print('='*70)
    print(f"{'Metric':<22} {'Baseline':>10} {'Variant':>10} {'Delta':>8}")
    print("-" * 55)

    for metric in metrics:
        b_scores = [r[metric] for r in baseline_results if r[metric] is not None]
        v_scores = [r[metric] for r in variant_results if r[metric] is not None]

        b_avg = sum(b_scores) / len(b_scores) if b_scores else None
        v_avg = sum(v_scores) / len(v_scores) if v_scores else None
        delta = (v_avg - b_avg) if (b_avg is not None and v_avg is not None) else None

        b_str = f"{b_avg:.2f}" if b_avg is not None else "N/A"
        v_str = f"{v_avg:.2f}" if v_avg is not None else "N/A"
        d_str = f"{delta:+.2f}" if delta is not None else "N/A"

        print(f"{metric:<22} {b_str:>10} {v_str:>10} {d_str:>8}")

    print(f"\n{'ID':<6} {'Baseline F/R/Rc/C':<22} {'Variant F/R/Rc/C':<22} {'Better?':<10}")
    print("-" * 65)

    b_by_id = {r["id"]: r for r in baseline_results}
    for v_row in variant_results:
        qid = v_row["id"]
        b_row = b_by_id.get(qid, {})

        b_scores_str = "/".join([str(b_row.get(m, "?")) for m in metrics])
        v_scores_str = "/".join([str(v_row.get(m, "?")) for m in metrics])

        b_total = sum(b_row.get(m, 0) or 0 for m in metrics)
        v_total = sum(v_row.get(m, 0) or 0 for m in metrics)
        better = "Variant" if v_total > b_total else ("Baseline" if b_total > v_total else "Tie")

        print(f"{qid:<6} {b_scores_str:<22} {v_scores_str:<22} {better:<10}")

    if output_csv:
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        csv_path = RESULTS_DIR / output_csv
        combined = baseline_results + variant_results
        if combined:
            with open(csv_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=combined[0].keys())
                writer.writeheader()
                writer.writerows(combined)
            print(f"\nKết quả đã lưu vào: {csv_path}")


# =============================================================================
# REPORT GENERATOR
# =============================================================================

def generate_scorecard_summary(results: List[Dict], label: str) -> str:
    """Tạo báo cáo tóm tắt scorecard dạng markdown."""
    metrics = ["faithfulness", "relevance", "context_recall", "completeness"]
    averages = {}
    for metric in metrics:
        scores = [r[metric] for r in results if r[metric] is not None]
        averages[metric] = sum(scores) / len(scores) if scores else None

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

    md = f"""# Scorecard: {label}
Generated: {timestamp}

## Summary

| Metric | Average Score |
|--------|--------------|
"""
    for metric, avg in averages.items():
        avg_str = f"{avg:.2f}/5" if avg is not None else "N/A"
        md += f"| {metric.replace('_', ' ').title()} | {avg_str} |\n"

    md += "\n## Per-Question Results\n\n"
    md += "| ID | Category | Faithful | Relevant | Recall | Complete | Notes |\n"
    md += "|----|----------|----------|----------|--------|----------|-------|\n"

    for r in results:
        notes = r.get("faithfulness_notes", "")[:60]
        md += (f"| {r['id']} | {r['category']} | {r.get('faithfulness', 'N/A')} | "
               f"{r.get('relevance', 'N/A')} | {r.get('context_recall', 'N/A')} | "
               f"{r.get('completeness', 'N/A')} | {notes} |\n")

    md += "\n## Answers\n\n"
    for r in results:
        md += f"### [{r['id']}] {r['query']}\n"
        md += f"**Answer:** {r['answer']}\n\n"
        md += f"**Expected:** {r['expected_answer']}\n\n"
        md += "---\n\n"

    return md


# =============================================================================
# GRADING RUN LOG GENERATOR
# =============================================================================

def run_grading_log(
    grading_questions_path: str,
    output_path: str = "logs/grading_run.json",
    retrieval_mode: str = "hybrid",
) -> None:
    """
    Chạy pipeline với grading_questions.json và lưu log.
    Dùng khi grading_questions.json được public lúc 17:00.
    """
    LOGS_DIR.mkdir(parents=True, exist_ok=True)

    with open(grading_questions_path, encoding="utf-8") as f:
        questions = json.load(f)

    log = []
    for q in questions:
        print(f"  Running: {q['id']} — {q['question'][:60]}...")
        try:
            result = rag_answer(q["question"], retrieval_mode=retrieval_mode, verbose=False)
            log.append({
                "id": q["id"],
                "question": q["question"],
                "answer": result["answer"],
                "sources": result["sources"],
                "chunks_retrieved": len(result["chunks_used"]),
                "retrieval_mode": result["config"]["retrieval_mode"],
                "timestamp": datetime.now().isoformat(),
            })
        except Exception as e:
            log.append({
                "id": q["id"],
                "question": q["question"],
                "answer": f"PIPELINE_ERROR: {e}",
                "sources": [],
                "chunks_retrieved": 0,
                "retrieval_mode": retrieval_mode,
                "timestamp": datetime.now().isoformat(),
            })

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)

    print(f"\nGrading log saved to: {output_path}")


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("Sprint 4: Evaluation & Scorecard")
    print("=" * 60)

    # Load test questions
    print(f"\nLoading test questions từ: {TEST_QUESTIONS_PATH}")
    with open(TEST_QUESTIONS_PATH, "r", encoding="utf-8") as f:
        test_questions = json.load(f)
    print(f"Tìm thấy {len(test_questions)} câu hỏi")

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    # --- Chạy Baseline ---
    print("\n--- Chạy Baseline (Dense) ---")
    baseline_results = run_scorecard(
        config=BASELINE_CONFIG,
        test_questions=test_questions,
        verbose=True,
    )
    baseline_md = generate_scorecard_summary(baseline_results, "baseline_dense")
    (RESULTS_DIR / "scorecard_baseline.md").write_text(baseline_md, encoding="utf-8")
    print(f"\nScorecard baseline lưu tại: {RESULTS_DIR / 'scorecard_baseline.md'}")

    # --- Chạy Variant ---
    print("\n--- Chạy Variant (Hybrid) ---")
    variant_results = run_scorecard(
        config=VARIANT_CONFIG,
        test_questions=test_questions,
        verbose=True,
    )
    variant_md = generate_scorecard_summary(variant_results, "variant_hybrid")
    (RESULTS_DIR / "scorecard_variant.md").write_text(variant_md, encoding="utf-8")
    print(f"\nScorecard variant lưu tại: {RESULTS_DIR / 'scorecard_variant.md'}")

    # --- A/B Comparison ---
    print("\n--- A/B Comparison ---")
    compare_ab(
        baseline_results,
        variant_results,
        output_csv="ab_comparison.csv"
    )

    print("\n\nSprint 4 hoàn thành!")
    print("Để chạy grading questions (sau 17:00):")
    print("  from eval import run_grading_log")
    print("  run_grading_log('data/grading_questions.json')")
