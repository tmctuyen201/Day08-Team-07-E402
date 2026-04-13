# Báo Cáo Cá Nhân — Lab Day 08: RAG Pipeline

**Họ và tên:** Nguyễn Thị Cẩm Nhung
**Vai trò trong nhóm:** Eval Owner  
**Ngày nộp:** 2026-04-13  

---

## 1. Tôi đã làm gì trong lab này?

Với vai trò Eval Owner, tôi chịu trách nhiệm Sprint 3 và 4, tập trung đánh giá chất lượng pipeline RAG.

Trong Sprint 3, tôi chuẩn bị 10 test questions với expected evidence, đảm bảo coverage đủ các category (SLA, Refund, Access Control, IT Helpdesk, HR Policy) và 3 difficulty levels. Đặc biệt, tôi thiết kế 2 câu test abstain mechanism (q09, q10) để kiểm tra khả năng pipeline từ chối trả lời khi thiếu thông tin.

Trong Sprint 4, tôi chạy evaluation với 4 metrics: Faithfulness, Answer Relevance, Context Recall, và Completeness. Tôi sử dụng LLM-as-Judge cho 3 metrics để tự động hóa chấm điểm. Sau đó, tôi tạo scorecard cho baseline (dense) và variant (hybrid), rồi chạy A/B comparison để tính delta.

Công việc của tôi cung cấp evidence về hiệu quả hybrid strategy cho Retrieval Owner và số liệu cho Documentation Owner viết tuning-log.md.

---

## 2. Điều tôi hiểu rõ hơn sau lab này

Sau lab này, tôi hiểu sâu hơn về **trade-off giữa các metrics trong RAG evaluation**. Ban đầu, tôi nghĩ variant tốt hơn sẽ cải thiện tất cả metrics, nhưng thực tế hybrid **KÉM HƠN** baseline ở tất cả metrics: Faithfulness giảm -0.40 (từ 3.60→3.20), Relevance giảm -0.10 (từ 4.00→3.90), và Completeness giảm -0.30 (từ 4.20→3.90).

Điều này xảy ra vì BM25 retrieve chunks có exact keyword nhưng không liên quan về ngữ nghĩa. Ví dụ, từ "escalation" xuất hiện ở cả sla_p1_2026.txt (đúng) và access_control_sop.txt (sai), khiến BM25 kéo sai chunk vào top-3. Dense search tốt hơn về ngữ nghĩa trong corpus nhỏ này.

Tôi cũng học được **LLM-as-Judge không nhất quán**. Một số câu có điểm Faithfulness khác nhau giữa các lần chạy dù temperature=0. Cần chạy evaluation nhiều lần và lấy trung bình.

---

## 3. Điều tôi ngạc nhiên hoặc gặp khó khăn

Điều ngạc nhiên nhất là **hybrid KÉM HƠN baseline ở TẤT CẢ metrics**. Tôi kỳ vọng hybrid sẽ cải thiện ít nhất một vài câu, nhưng kết quả cho thấy Faithfulness giảm -0.40, Relevance giảm -0.10, Completeness giảm -0.30. Đặc biệt q06 fail hoàn toàn (Completeness 5→1).

Khi debug, baseline trả lời đúng về "ticket P1 escalate lên Senior Engineer trong 10 phút", nhưng variant trả lời SAI về "cấp quyền tạm thời 24 giờ" từ access_control_sop.txt. Root cause: BM25 bắt từ "escalation" xuất hiện nhiều trong access_control_sop, và RRF fusion với sparse_weight=0.4 kéo sai chunk lên top-3. Với corpus nhỏ 29 chunks, dense đã đủ tốt, thêm BM25 chỉ tạo noise.

Khó khăn lớn nhất là **thiết kế expected_answer cho abstain cases**. Với q09 (ERR-403-AUTH), tôi quyết định expected answer có gợi ý "liên hệ IT Helpdesk" để test xem pipeline có infer được từ context không. Kết quả: cả baseline và variant đều Faithfulness=1 vì abstain quá ngắn gọn.

---

## 4. Phân tích một câu hỏi trong scorecard

**Câu hỏi:** q06 — "Escalation trong sự cố P1 diễn ra như thế nào?"

**Baseline (Dense) — Completeness 5/5:**
Pipeline trả lời đúng: "Trong sự cố P1, quy trình escalation diễn ra như sau: nếu không có phản hồi trong 10 phút kể từ khi ticket được tạo, ticket sẽ tự động được escalate lên Senior Engineer". Dense search retrieve đúng chunk từ sla_p1_2026.txt vì embedding similarity cao với query về "P1 escalation". Faithfulness=2 vì LLM-as-Judge cho rằng có thêm chi tiết về "thông báo stakeholder" không rõ ràng trong context.

**Variant (Hybrid) — Completeness 1/5:**
Pipeline trả lời SAI hoàn toàn: "Escalation trong sự cố P1 diễn ra theo quy trình khẩn cấp như sau: 1. On-call IT Admin có thể cấp quyền tạm thời (tối đa 24 giờ) sau khi được Tech Lead phê duyệt bằng lời...". Đây là nội dung từ access_control_sop.txt Section 4 về emergency access escalation, không liên quan đến P1 ticket escalation.

**Root cause — Retrieval lỗi:**
BM25 bắt từ "escalation" xuất hiện ở cả hai tài liệu. Trong access_control_sop.txt, từ "escalation" xuất hiện nhiều lần (emergency escalation, escalation process, escalation approval), khiến BM25 score cao hơn. RRF fusion với dense_weight=0.6 và sparse_weight=0.4 không đủ để lọc noise này, dẫn đến sai chunk được đưa vào top-3.

**Generation không sai:** LLM generate đúng từ retrieved context, nhưng context đã sai từ đầu.

**Kết luận:** Lỗi nằm ở retrieval stage, không phải generation. Hybrid retrieval với corpus nhỏ (29 chunks) tạo ra nhiều noise hơn là cải thiện. Baseline dense đã đủ tốt với Context Recall 5.00/5. Nên sử dụng **baseline (dense)** cho production.

---

## 5. Nếu có thêm thời gian, tôi sẽ làm gì?

**1. Thêm cross-encoder rerank sau hybrid retrieval**

Evidence: q06 Completeness giảm từ 5→1, q03 Faithfulness giảm từ 2→1, q10 Faithfulness giảm từ 3→1 vì BM25 kéo sai chunk. Cross-encoder sẽ chấm lại từng cặp (query, chunk) và loại bỏ chunks có keyword match nhưng không liên quan về ngữ nghĩa. Điều này có thể giữ được lợi ích của hybrid (bắt exact term) mà không mất Faithfulness và Completeness.

**2. Thử tăng dense_weight lên 0.8 hoặc chỉ dùng dense cho corpus nhỏ**

Evidence: Với corpus chỉ 29 chunks, baseline dense đã đạt Context Recall 5.00/5 (retrieve đúng 100% expected sources). Thêm BM25 với sparse_weight=0.4 tạo ra nhiều noise hơn là cải thiện. Nên thử dense_weight=0.8/sparse_weight=0.2 hoặc chỉ dùng dense cho corpus nhỏ, chỉ bật hybrid khi corpus >100 chunks.

