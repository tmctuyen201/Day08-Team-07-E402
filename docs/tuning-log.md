# Tuning Log — RAG Pipeline (Day 08 Lab)

> A/B Rule: Chỉ đổi MỘT biến mỗi lần.

---

## Baseline (Sprint 2)

**Ngày:** 2026-04-13
**Config:**
```
retrieval_mode = "dense"
embedding_model = "paraphrase-multilingual-MiniLM-L12-v2"
chunk_size = 400 tokens (~1600 chars)
overlap = 80 tokens (~320 chars)
top_k_search = 10
top_k_select = 3
use_rerank = False
llm_model = "gpt-4o-mini"
temperature = 0
```

**Scorecard Baseline:**
| Metric | Average Score |
|--------|--------------|
| Faithfulness | 3.40/5 |
| Answer Relevance | 3.90/5 |
| Context Recall | 5.00/5 |
| Completeness | 4.10/5 |

**Câu hỏi yếu nhất (dự đoán từ phân tích corpus):**

1. **q07 — "Approval Matrix để cấp quyền là tài liệu nào?"**
   - Context recall thấp vì dense search dùng embedding similarity, có thể bỏ lỡ exact term "Approval Matrix" khi tài liệu đã đổi tên thành "Access Control SOP".
   - Đây là alias query — điểm yếu kinh điển của pure dense retrieval.

2. **q09 — "ERR-403-AUTH là lỗi gì?"**
   - Không có thông tin trong docs → pipeline phải abstain.
   - Dense có thể retrieve các chunk về authentication nhưng không có exact answer.
   - Rủi ro hallucination cao nếu prompt không đủ grounding.

3. **q06 — "Escalation trong sự cố P1 diễn ra như thế nào?"**
   - Cần retrieve đúng section về escalation trong sla_p1_2026.txt.
   - Dense thường tốt với câu này nhưng cần kiểm tra.

**Giả thuyết nguyên nhân (Error Tree):**
- [x] Retrieval: Dense bỏ lỡ exact keyword / alias (q07, q09)
- [ ] Indexing: Chunking cắt giữa điều khoản
- [ ] Retrieval: Top-k quá ít → thiếu evidence
- [ ] Generation: Prompt không đủ grounding

---

## Variant 1 (Sprint 3) — Hybrid Retrieval

**Ngày:** 2026-04-13
**Biến thay đổi:** `retrieval_mode`: `"dense"` → `"hybrid"` (Dense + BM25 với RRF)
**Tất cả tham số khác giữ nguyên.**

**Lý do chọn biến này:**

Từ phân tích baseline, câu hỏi yếu nhất là q07 (alias query: "Approval Matrix" → "Access Control SOP") và q09 (exact term: "ERR-403-AUTH"). Cả hai đều là trường hợp mà dense search dựa trên embedding similarity có thể thất bại vì:

1. "Approval Matrix" và "Access Control SOP" có nghĩa tương đồng nhưng surface form khác nhau. Dense có thể tìm được qua ngữ nghĩa, nhưng BM25 sẽ bắt được exact term "Approval Matrix" trong ghi chú tài liệu (`Ghi chú: Tài liệu này trước đây có tên "Approval Matrix for System Access"`).

2. Corpus lẫn lộn ngôn ngữ tự nhiên (chính sách, quy trình) và tên kỹ thuật (`P1`, `Level 3`, `ERR-403`). Hybrid RRF kết hợp điểm mạnh của cả hai.

**Config thay đổi:**
```
retrieval_mode = "hybrid"   # THAY ĐỔI DUY NHẤT
dense_weight = 0.6
sparse_weight = 0.4
# Tất cả tham số còn lại giữ nguyên như baseline
```

**Scorecard Variant 1:**
| Metric | Baseline | Variant 1 | Delta |
|--------|----------|-----------|-------|
| Faithfulness | 3.40/5 | 3.70/5 | +0.30 |
| Answer Relevance | 3.90/5 | 4.00/5 | +0.10 |
| Context Recall | 5.00/5 | 5.00/5 | +0.00 |
| Completeness | 4.10/5 | 3.90/5 | -0.20 |

**Nhận xét:**
Hybrid cải thiện Faithfulness (+0.30) và Answer Relevance (+0.10). Context Recall đạt ceiling 5.00/5 ở cả hai — corpus nhỏ 29 chunks nên dense đã đủ tốt.

Câu cải thiện rõ nhất: q07 (Approval Matrix alias) — Faithfulness tăng 3→5 vì BM25 bắt được exact term "Approval Matrix" trong ghi chú tài liệu. q03, q04, q09 cũng cải thiện.

Câu kém hơn: q06 (P1 escalation) — hybrid mang về chunk từ access_control_sop thay vì sla_p1_2026, Completeness giảm 4→1. BM25 noise kéo sai chunk vào top-3 khi query có từ "escalation" xuất hiện ở cả hai tài liệu.

**Kết luận:**
Hybrid tốt hơn baseline về Faithfulness (+0.30) và Answer Relevance (+0.10). Bằng chứng: q07 Faithfulness 3→5, q03/q04/q09 cải thiện. Trade-off: Completeness giảm -0.20 do BM25 noise ở q06. Nếu cần tối ưu Completeness, bước tiếp theo là thêm cross-encoder rerank để lọc noise từ BM25.

---

## Tóm tắt học được

1. **Lỗi phổ biến nhất trong pipeline này là gì?**
   Faithfulness thấp (3.40/5 baseline) — LLM-as-Judge phát hiện một số câu trả lời có thông tin không hoàn toàn grounded vào retrieved context (đặc biệt q03, q06). Nguyên nhân: model đôi khi thêm chi tiết từ model knowledge dù prompt yêu cầu evidence-only.

2. **Biến nào có tác động lớn nhất tới chất lượng?**
   Retrieval strategy: hybrid cải thiện Faithfulness (+0.30) và Answer Relevance (+0.10) so với dense. Tuy nhiên có trade-off: Completeness giảm -0.20 do BM25 noise ở q06. Chunking strategy (section-based) là nền tảng — Context Recall đạt 5.00/5 ở cả hai mode nhờ chunk không bị cắt giữa điều khoản.

3. **Nếu có thêm 1 giờ, nhóm sẽ thử gì tiếp theo?**
   Thêm cross-encoder rerank sau hybrid. Kết quả eval cho thấy q06 Completeness giảm 4→1 ở hybrid vì BM25 kéo chunk sai vào top-3. Cross-encoder sẽ chấm lại từng cặp (query, chunk) và loại bỏ noise, giữ được lợi ích của hybrid mà không mất Completeness.
