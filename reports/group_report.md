# Group Report — Lab Day 08: RAG Pipeline

**Ngày:** 2026-04-13

---

## 1. Quyết định kỹ thuật cấp nhóm

### Chunking: Section-based với paragraph fallback

Chúng tôi chọn section-based chunking (split theo `=== ... ===`) thay vì fixed-size chunking vì tất cả 5 tài liệu đều có cấu trúc heading rõ ràng. Mỗi section chứa một điều khoản hoàn chỉnh — cắt theo section đảm bảo chunk không bị cắt giữa quy định. Với section quá dài, fallback sang paragraph-based splitting với overlap 80 tokens để giữ ngữ cảnh liên tục.

### Embedding: Sentence Transformers (local)

Chọn `paraphrase-multilingual-MiniLM-L12-v2` vì hỗ trợ tiếng Việt tốt, chạy local không cần API key, và phù hợp với corpus nội bộ. Đây là quyết định thực tế — không phụ thuộc vào API key khi demo.

### Retrieval Variant: Hybrid (Dense + BM25 RRF)

Sau khi phân tích corpus, nhận thấy tài liệu có cả ngôn ngữ tự nhiên lẫn exact keyword kỹ thuật (`P1`, `Level 3`, `ERR-403`, `Approval Matrix`). Hybrid RRF với dense_weight=0.6 và sparse_weight=0.4 kết hợp điểm mạnh của cả hai. Chỉ thay đổi MỘT biến (retrieval_mode) để A/B comparison có ý nghĩa.

### Evaluation: LLM-as-Judge

Implement LLM-as-Judge cho 3/4 metrics để tự động hóa evaluation. Context Recall dùng exact source matching (deterministic, không cần LLM). Điều này cho phép chạy scorecard nhanh với 10 câu hỏi mà không cần chấm thủ công.

---

## 2. Kết quả A/B Comparison

| Metric | Baseline (Dense) | Variant (Hybrid) | Delta |
|--------|-----------------|-----------------|-------|
| Faithfulness | 3.60/5 | 3.20/5 | **-0.40** |
| Answer Relevance | 4.00/5 | 3.90/5 | **-0.10** |
| Context Recall | 5.00/5 | 5.00/5 | +0.00 |
| Completeness | 4.20/5 | 3.90/5 | **-0.30** |

**Câu hỏi kém hơn rõ nhất ở variant:** q06 (P1 escalation) — hybrid Completeness giảm từ 5→1 vì BM25 retrieve chunk từ access_control_sop.txt về "cấp quyền tạm thời 24 giờ" thay vì sla_p1_2026.txt về "escalate lên Senior Engineer trong 10 phút". Từ "escalation" xuất hiện ở cả hai tài liệu, BM25 không phân biệt được ngữ nghĩa. q03 Faithfulness giảm 2→1, q10 Faithfulness giảm 3→1 cũng do BM25 noise.

**Câu hỏi không cải thiện:** q07 (Approval Matrix alias query) và q09 (ERR-403-AUTH abstain) — cả baseline và variant đều abstain đúng với điểm tương tự. Không có câu nào cải thiện rõ ràng ở variant.

**Nhận xét tổng thể:** Hybrid **KÉM HƠN** baseline ở tất cả metrics. Với corpus nhỏ 29 chunks, baseline dense đã đạt Context Recall 5.00/5 (retrieve đúng 100% expected sources). Thêm BM25 tạo ra nhiều noise hơn là cải thiện vì BM25 bắt exact keyword nhưng không hiểu ngữ nghĩa. **Quyết định: Sử dụng baseline (dense) cho production.**

---

## 3. Bài học kỹ thuật

- **Chunking > LLM:** Chất lượng chunking quyết định ceiling của pipeline. LLM tốt không bù được retrieval tệ.
- **Abstain là feature, không phải bug:** Pipeline trả về "không đủ dữ liệu" đúng lúc quan trọng hơn pipeline luôn có câu trả lời.
- **A/B rule quan trọng:** Chỉ đổi một biến mỗi lần mới biết biến nào thực sự tạo ra cải thiện.
