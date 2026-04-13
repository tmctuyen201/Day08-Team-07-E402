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
| Faithfulness | 3.40/5 | 3.70/5 | +0.30 |
| Answer Relevance | 3.90/5 | 4.00/5 | +0.10 |
| Context Recall | 5.00/5 | 5.00/5 | +0.00 |
| Completeness | 4.10/5 | 3.90/5 | -0.20 |

**Câu hỏi cải thiện rõ nhất:** q07 (Approval Matrix alias query) — hybrid Faithfulness tăng từ 3→5 vì BM25 bắt được exact term "Approval Matrix" trong ghi chú tài liệu, giúp pipeline abstain đúng hơn. q03, q04, q09 cũng cải thiện nhờ hybrid retrieve đúng chunk hơn.

**Câu hỏi kém hơn ở variant:** q06 (P1 escalation) — hybrid mang về chunk từ access_control_sop thay vì sla_p1_2026, làm Completeness giảm từ 4→1. Đây là trường hợp BM25 noise kéo sai chunk vào top-3.

**Nhận xét tổng thể:** Hybrid cải thiện Faithfulness (+0.30) và Answer Relevance (+0.10), nhưng giảm nhẹ Completeness (-0.20) do BM25 đôi khi mang về chunk ít liên quan về ngữ nghĩa. Context Recall đạt ceiling 5.00/5 ở cả hai — corpus nhỏ 29 chunks nên dense đã đủ tốt để retrieve đúng source.

---

## 3. Bài học kỹ thuật

- **Chunking > LLM:** Chất lượng chunking quyết định ceiling của pipeline. LLM tốt không bù được retrieval tệ.
- **Abstain là feature, không phải bug:** Pipeline trả về "không đủ dữ liệu" đúng lúc quan trọng hơn pipeline luôn có câu trả lời.
- **A/B rule quan trọng:** Chỉ đổi một biến mỗi lần mới biết biến nào thực sự tạo ra cải thiện.
