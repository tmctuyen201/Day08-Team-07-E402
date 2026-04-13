# Báo Cáo Cá Nhân — Lab Day 08: RAG Pipeline

**Họ và tên:** Kiro AI
**Vai trò trong nhóm:** Tech Lead + Retrieval Owner + Eval Owner + Documentation Owner
**Ngày nộp:** 2026-04-13
**Độ dài yêu cầu:** 500–800 từ

---

## 1. Tôi đã làm gì trong lab này?

Tôi đảm nhận toàn bộ pipeline từ Sprint 1 đến Sprint 4. Cụ thể:

**Sprint 1 (Indexing):** Implement `preprocess_document()` để extract metadata từ header file (Source, Department, Effective Date, Access), `chunk_document()` theo section heading `=== ... ===` trước rồi fallback sang paragraph-based splitting với overlap 80 tokens. Implement `get_embedding()` dùng `paraphrase-multilingual-MiniLM-L12-v2` (Sentence Transformers local) và `build_index()` để upsert vào ChromaDB với cosine similarity.

**Sprint 2 (Baseline RAG):** Implement `retrieve_dense()` query ChromaDB với embedding, `call_llm()` hỗ trợ cả OpenAI và Gemini, và `rag_answer()` pipeline hoàn chỉnh với grounded prompt ép citation và abstain.

**Sprint 3 (Hybrid Retrieval):** Implement `retrieve_sparse()` dùng BM25Okapi với cache, `retrieve_hybrid()` dùng Reciprocal Rank Fusion (RRF) với dense_weight=0.6 và sparse_weight=0.4. Chọn hybrid vì corpus có cả ngôn ngữ tự nhiên lẫn exact keyword kỹ thuật.

**Sprint 4 (Evaluation):** Implement LLM-as-Judge cho 3/4 metrics (Faithfulness, Answer Relevance, Completeness), Context Recall dùng exact source matching. Implement `run_scorecard()`, `compare_ab()`, và `run_grading_log()` cho grading questions.

---

## 2. Điều tôi hiểu rõ hơn sau lab này

**Chunking là quyết định quan trọng nhất trong RAG, không phải LLM.** Trước lab, tôi nghĩ chất lượng LLM quyết định output. Sau khi implement, tôi nhận ra nếu chunk cắt giữa điều khoản — ví dụ cắt giữa "Điều 3: Ngoại lệ không được hoàn tiền" — thì dù LLM tốt đến đâu cũng không trả lời được vì context đã thiếu. Section-based chunking giải quyết vấn đề này bằng cách tôn trọng ranh giới tự nhiên của tài liệu.

**Hybrid retrieval giải quyết vấn đề alias mismatch.** Dense search dựa trên embedding similarity — tốt cho câu hỏi paraphrase nhưng có thể bỏ lỡ exact term. Khi tài liệu đổi tên từ "Approval Matrix" thành "Access Control SOP", dense search có thể tìm được qua ngữ nghĩa, nhưng BM25 bắt được exact term "Approval Matrix" trong ghi chú tài liệu. RRF kết hợp cả hai mà không cần tune threshold phức tạp.

---

## 3. Điều tôi ngạc nhiên hoặc gặp khó khăn

Điều ngạc nhiên nhất là **abstain mechanism khó hơn tưởng**. Ban đầu tôi nghĩ chỉ cần viết "If context is insufficient, say you don't know" trong prompt là đủ. Thực tế, LLM vẫn có xu hướng "helpful hallucination" — đưa ra câu trả lời có vẻ hợp lý từ model knowledge thay vì abstain. Phải viết prompt rõ ràng hơn: "explicitly state that the information is not available in the provided documents" và "Do not make up information" mới đủ mạnh.

Khó khăn kỹ thuật: ChromaDB cosine distance trả về `1 - similarity`, không phải similarity trực tiếp. Nếu không chú ý, score sẽ bị đảo ngược — chunk kém nhất lại có score cao nhất. Phải convert: `score = 1.0 - distance`.

---

## 4. Phân tích một câu hỏi trong scorecard

**Câu hỏi q07:** "Approval Matrix để cấp quyền hệ thống là tài liệu nào?"

**Phân tích:**

Đây là câu hỏi alias query — người dùng dùng tên cũ "Approval Matrix" trong khi tài liệu hiện tại có tên "Access Control SOP". Tài liệu `access_control_sop.txt` có ghi chú: *"Tài liệu này trước đây có tên 'Approval Matrix for System Access'"*.

**Baseline (dense):** Có thể thất bại ở retrieval nếu embedding của "Approval Matrix" không đủ gần với embedding của "Access Control SOP". Context recall = thấp nếu chunk chứa ghi chú tên cũ không được retrieve.

**Failure mode:** Retrieval — dense search không bắt được exact term "Approval Matrix" trong ghi chú tài liệu nếu embedding space không capture được sự tương đồng.

**Variant (hybrid):** BM25 sẽ bắt được exact term "Approval Matrix" trong ghi chú tài liệu vì BM25 là keyword matching. RRF kết hợp với dense score sẽ đẩy chunk đó lên top. Context recall dự kiến tăng từ 0 lên 5/5.

**Root cause:** Indexing đúng (ghi chú tên cũ được index), nhưng retrieval baseline (dense only) không đủ để bắt exact keyword. Fix: hybrid retrieval.

---

## 5. Nếu có thêm thời gian, tôi sẽ làm gì?

Từ scorecard, nếu context recall của q06 (P1 escalation + cấp quyền tạm thời) vẫn thấp sau hybrid, tôi sẽ thêm **cross-encoder rerank**: hybrid mang về top-10 candidates đa dạng, nhưng RRF score không phản ánh chính xác "chunk nào trả lời câu hỏi này nhất". Cross-encoder `ms-marco-MiniLM-L-6-v2` chấm lại từng cặp (query, chunk) sẽ chính xác hơn, đặc biệt cho câu hỏi multi-hop cần kết hợp thông tin từ nhiều section.

---

*File: `reports/individual/kiro_ai.md`*
