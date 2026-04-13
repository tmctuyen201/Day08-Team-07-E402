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
| Faithfulness | 3.60/5 |
| Answer Relevance | 4.00/5 |
| Context Recall | 5.00/5 |
| Completeness | 4.20/5 |

**Câu hỏi yếu nhất (dự đoán từ phân tích corpus):**

1. **q07 — "Approval Matrix để cấp quyền là tài liệu nào?"**
   - Context recall có thể thấp vì dense search dùng embedding similarity, có thể bỏ lỡ exact term "Approval Matrix" khi tài liệu đã đổi tên thành "Access Control SOP".
   - Đây là alias query — điểm yếu kinh điển của pure dense retrieval.
   - Kết quả thực tế: Cả baseline và variant đều Relevance=1, Completeness=1 vì pipeline abstain (không tìm thấy "Approval Matrix" trong tài liệu).

2. **q09 — "ERR-403-AUTH là lỗi gì?"**
   - Không có thông tin trong docs → pipeline phải abstain.
   - Dense có thể retrieve các chunk về authentication nhưng không có exact answer.
   - Rủi ro hallucination cao nếu prompt không đủ grounding.
   - Kết quả thực tế: Cả baseline và variant đều Faithfulness=1, Relevance=1 vì abstain đúng nhưng quá ngắn gọn.

3. **q06 — "Escalation trong sự cố P1 diễn ra như thế nào?"**
   - Cần retrieve đúng section về escalation trong sla_p1_2026.txt.
   - Dense thường tốt với câu này.
   - Kết quả thực tế: Baseline Completeness=5 (đúng), Variant Completeness=1 (sai hoàn toàn - retrieve từ access_control_sop thay vì sla_p1_2026).

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
| Faithfulness | 3.60/5 | 3.20/5 | **-0.40** |
| Answer Relevance | 4.00/5 | 3.90/5 | **-0.10** |
| Context Recall | 5.00/5 | 5.00/5 | +0.00 |
| Completeness | 4.20/5 | 3.90/5 | **-0.30** |

**Nhận xét:**
Hybrid **KÉM HƠN** baseline ở tất cả metrics chính. Faithfulness giảm -0.40, Answer Relevance giảm -0.10, Completeness giảm -0.30. Context Recall đạt ceiling 5.00/5 ở cả hai — corpus nhỏ 29 chunks nên dense đã đủ tốt.

Câu kém hơn rõ nhất: 
- **q06** (P1 escalation): Completeness giảm 5→1. Hybrid retrieve chunk từ access_control_sop.txt về "cấp quyền tạm thời 24 giờ" thay vì sla_p1_2026.txt về "escalate lên Senior Engineer trong 10 phút". BM25 bắt từ "escalation" xuất hiện nhiều trong access_control_sop, RRF fusion kéo sai chunk vào top-3.
- **q03** (Level 3 approval): Faithfulness giảm 2→1.
- **q10** (VIP refund): Faithfulness giảm 3→1.

Câu cải thiện: Không có câu nào cải thiện rõ ràng. q01, q02, q05, q08 giữ nguyên điểm. q07, q09 vẫn abstain đúng ở cả hai mode.

**Kết luận:**
Hybrid KÉM HƠN baseline (-0.40 Faithfulness, -0.30 Completeness). Với corpus nhỏ 29 chunks, baseline dense đã đạt Context Recall 5.00/5 (retrieve đúng 100% expected sources). Thêm BM25 tạo ra nhiều noise hơn là cải thiện vì:
1. BM25 bắt exact keyword nhưng không hiểu ngữ nghĩa → kéo sai chunk (ví dụ: "escalation" trong access_control vs sla)
2. Corpus nhỏ → dense embedding đã đủ để phân biệt các tài liệu
3. RRF fusion với sparse_weight=0.4 quá cao cho corpus này

**Quyết định cuối cùng: Sử dụng BASELINE (dense) cho production.** Hybrid chỉ nên dùng khi corpus >100 chunks hoặc có nhiều exact keyword/alias không thể handle bằng embedding.

---

## Tóm tắt học được

1. **Lỗi phổ biến nhất trong pipeline này là gì?**
   Faithfulness thấp (3.60/5 baseline, 3.20/5 hybrid) — LLM-as-Judge phát hiện một số câu trả lời có thông tin không hoàn toàn grounded vào retrieved context (đặc biệt q03 Faithfulness=2, q06 Faithfulness=2). Nguyên nhân: model đôi khi thêm chi tiết từ model knowledge dù prompt yêu cầu evidence-only. Hybrid làm tệ hơn vì BM25 kéo sai chunk, khiến LLM generate từ context không liên quan.

2. **Biến nào có tác động lớn nhất tới chất lượng?**
   Retrieval strategy: hybrid **KÉM HƠN** baseline (-0.40 Faithfulness, -0.30 Completeness). Với corpus nhỏ 29 chunks, dense đã đủ tốt (Context Recall 5.00/5). Thêm BM25 tạo noise vì bắt exact keyword không hiểu ngữ nghĩa. Chunking strategy (section-based) là nền tảng quan trọng nhất — Context Recall đạt 5.00/5 ở cả hai mode nhờ chunk không bị cắt giữa điều khoản.

3. **Nếu có thêm 1 giờ, nhóm sẽ thử gì tiếp theo?**
   Thêm cross-encoder rerank sau hybrid để lọc BM25 noise. Kết quả eval cho thấy q06 Completeness giảm 5→1, q03 Faithfulness giảm 2→1, q10 Faithfulness giảm 3→1 vì BM25 kéo chunk sai vào top-3. Cross-encoder sẽ chấm lại từng cặp (query, chunk) và loại bỏ noise, giữ được lợi ích của hybrid (bắt exact term) mà không mất Faithfulness và Completeness. Hoặc đơn giản hơn: chỉ dùng dense cho corpus <50 chunks, chỉ bật hybrid khi corpus lớn hơn.
