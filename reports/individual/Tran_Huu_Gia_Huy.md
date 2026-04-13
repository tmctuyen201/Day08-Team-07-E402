# Báo Cáo Cá Nhân — Lab Day 08: RAG Pipeline

**Họ và tên:** Trần Hữu Gia Huy
**Vai trò trong nhóm:** Documentation Owner
**Ngày nộp:** 13/04/2026
**Độ dài yêu cầu:** 500–800 từ

---

## 1. Tôi đã làm gì trong lab này? (100-150 từ)

Trong lab này tôi đảm nhận vai trò Documentation Owner, chịu trách nhiệm chính ở Sprint 4: hoàn thiện `docs/architecture.md`, `docs/tuning-log.md`, và `reports/group_report.md`. Cụ thể, tôi ghi lại toàn bộ quyết định thiết kế pipeline — từ lý do chọn section-based chunking, embedding model, đến phân tích A/B giữa dense và hybrid retrieval. Tôi cũng điền scorecard cho cả baseline lẫn variant, phân tích câu hỏi yếu nhất (q07, q09), và viết phần "bài học kỹ thuật" cho báo cáo nhóm.

Ngoài phần documentation, tôi tự chạy toàn bộ pipeline từ Sprint 1 đến Sprint 4 để hiểu rõ từng bước trước khi viết — không chỉ ghi lại kết quả mà còn tự tay implement và debug để đảm bảo những gì viết ra là chính xác.

---

## 2. Điều tôi hiểu rõ hơn sau lab này (100-150 từ)

Điều tôi hiểu rõ nhất sau lab là **tại sao chunking lại quan trọng hơn cả LLM**. Trước đây tôi nghĩ chất lượng model là yếu tố quyết định — nhưng khi tự chạy pipeline, tôi thấy rõ: nếu chunk cắt giữa một điều khoản, LLM dù tốt đến đâu cũng không thể trả lời đúng vì context đã thiếu. Section-based chunking giải quyết điều này bằng cách tôn trọng ranh giới tự nhiên của tài liệu.

Điều thứ hai là **cách LLM-as-Judge hoạt động trong vòng lặp eval**. Trước lab tôi chỉ biết khái niệm, nhưng sau khi đọc kỹ `eval.py` và scorecard, tôi hiểu tại sao Faithfulness và Completeness lại có thể đi ngược chiều nhau — một câu trả lời ngắn, grounded tốt có thể bị trừ điểm Completeness nếu thiếu chi tiết so với expected answer.

---

## 3. Điều tôi ngạc nhiên hoặc gặp khó khăn (100-150 từ)

Phần khó nhất với tôi là **implement thuật toán Reciprocal Rank Fusion (RRF)**. Về lý thuyết, RRF nghe đơn giản: lấy rank từ hai danh sách, tính `1 / (k + rank)`, cộng lại rồi sort. Nhưng khi thực tế implement, có nhiều điểm không rõ ràng: dense search trả về distance (không phải similarity), BM25 trả về score tuyệt đối không cùng thang đo với dense — hai danh sách này không thể cộng trực tiếp mà phải convert về rank trước. Tôi mất khá nhiều thời gian debug vì ban đầu cộng nhầm score thay vì rank, dẫn đến kết quả hybrid bị lệch hoàn toàn.

Sau khi sửa đúng, kết quả hybrid rõ ràng hơn hẳn — đặc biệt với query ERR-403-AUTH, hybrid retrieve đúng chunk từ `helpdesk-faq.md` trong khi dense baseline lại trả về chunk từ `access-control-sop.md`. Đó là lúc tôi thực sự hiểu RRF hoạt động như thế nào.

---

## 4. Phân tích một câu hỏi trong scorecard (150-200 từ)

**Câu hỏi q07:** "Approval Matrix để cấp quyền hệ thống là tài liệu nào?"

Đây là câu hỏi alias query — người dùng dùng tên cũ "Approval Matrix" trong khi tài liệu hiện tại đã đổi tên thành "Access Control SOP". File `access_control_sop.txt` có ghi chú: *"Tài liệu này trước đây có tên 'Approval Matrix for System Access'"*.

**Baseline (dense):** Retriever tìm được `access-control-sop.md` nhưng không lấy đúng chunk chứa ghi chú tên cũ. LLM trả lời "Tôi không biết" — đúng về mặt grounding nhưng sai về mặt thực tế vì thông tin có trong docs, chỉ là retriever không lấy được chunk đúng. Faithfulness = 3, Completeness thấp.

**Lỗi nằm ở retrieval:** Dense embedding không capture được sự tương đồng giữa "Approval Matrix" và "Access Control SOP" đủ mạnh để đẩy chunk có ghi chú tên cũ lên top-3.

**Variant (hybrid):** BM25 bắt được exact term "Approval Matrix" trong ghi chú tài liệu, RRF đẩy chunk đó lên top. LLM có đủ context để trả lời đúng. Faithfulness tăng từ 3 lên 5 — đây là câu cải thiện rõ nhất trong toàn bộ scorecard.

---

## 5. Nếu có thêm thời gian, tôi sẽ làm gì? (50-100 từ)

Từ scorecard, q06 (P1 escalation) là câu duy nhất bị hybrid làm tệ hơn — Completeness giảm từ 4 xuống 1 vì BM25 kéo chunk từ `access_control_sop` vào top-3 thay vì `sla_p1_2026`. Tôi sẽ thêm **cross-encoder rerank** sau bước hybrid: lấy top-10 từ RRF, rồi dùng cross-encoder chấm lại từng cặp (query, chunk) để loại noise. Điều này giữ được lợi ích của hybrid mà không mất Completeness ở các câu có từ khóa xuất hiện ở nhiều tài liệu.

---

*File: `reports/individual/tran_huu_gia_huy.md`*
