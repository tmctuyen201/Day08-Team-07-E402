# Báo Cáo Cá Nhân — Lab Day 08: RAG Pipeline

**Họ và tên:** Trịnh Đắc Phú  
**Vai trò trong nhóm:** Retrieval Owner
**Ngày nộp:** 13/04/2026  
**Độ dài yêu cầu:** 500–800 từ

---

## 1. Tôi đã làm gì trong lab này? (100-150 từ)

Trong lab này, tôi đảm nhận vai trò Tech Lead và Retrieval Owner, tập trung chủ yếu vào **Sprint 1: Build RAG Index**. Công việc chính của tôi là tái cấu trúc file `index.py` để tối ưu hóa quy trình tiền xử lý và chia nhỏ tài liệu (chunking). 

Cụ thể, tôi đã:
- **Cải thiện Preprocessing**: Viết lại logic xử lý header để tránh mất tiêu đề tài liệu khi chúng được viết hoa toàn bộ và sửa lỗi bỏ qua dòng trắng sai chỗ.
- **Tối ưu Chunking**: Triển khai logic chia nhỏ đoạn văn thông minh. Nếu một đoạn văn vượt quá `CHUNK_SIZE`, nó sẽ được cắt nhỏ dựa trên ký tự với phần overlap (gối đầu) chính xác, thay vì để nguyên một chunk khổng lồ như trước.
- **Mở rộng định dạng**: Bổ sung khả năng tự động tìm kiếm và xử lý các file `.pdf` và `.docx`, giúp pipeline không còn bị giới hạn ở chỉ file `.txt`.
- **Kiểm tra chất lượng**: Viết bộ test script để kiểm chứng tính đúng đắn của vector embedding và metadata coverage.

Công việc của tôi là nền tảng quan trọng giúp Retrieval đạt được độ phủ thông tin tốt nhất cho các bước tiếp theo của nhóm.

---

## 2. Điều tôi hiểu rõ hơn sau lab này (100-150 từ)

Sau lab này, tôi thực sự hiểu rõ hơn về **Chunking Strategy** và **Metadata Enrichment**. 

Trước đây, tôi nghĩ chunking chỉ đơn giản là cắt văn bản thành các đoạn bằng nhau. Tuy nhiên, qua thực tế triển khai, tôi nhận ra rằng việc cắt theo ranh giới tự nhiên (heading, paragraph) kết hợp với **Character-based fallback** là cực kỳ quan trọng để không làm gãy nội dung logic. Tôi cũng hiểu rõ hơn về tầm quan trọng của Metadata. Việc gắn thêm `department`, `section`, và bảo toàn `effective_date` như những "mỏ neo" thông tin giúp việc truy xuất sau này không chỉ dựa vào vector similarity mà còn có thể lọc chính xác theo ngữ cảnh nghiệp vụ (filtering). Điều này giúp hệ thống RAG không chỉ tìm thấy thông tin tương tự mà còn tìm thấy thông tin *đúng* và *còn hiệu lực*.

---

## 3. Điều tôi ngạc nhiên hoặc gặp khó khăn (100-150 từ)

Điều làm tôi ngạc nhiên nhất là tính "không nhất quán" của dữ liệu thô. Ban đầu, tôi giả định mọi file đều tuân thủ cấu trúc header `=== ... ===`. Nhưng thực tế, có những file thiếu dòng này hoặc tiêu đề nằm ngay dòng đầu tiên khiến script cũ bỏ qua sạch vì logic `isupper()`. 

Khó khăn lớn nhất tôi gặp phải là lỗi logic trong biến `header_done`. Nếu không tìm thấy dấu phân cách, script sẽ coi toàn bộ file là header và lọc bỏ hầu hết nội dung quan trọng. Việc debug để tìm ra lý do tại sao index chỉ có 1-2 chunks thay vì 30 chunks đã lấy đi khá nhiều thời gian. Tôi đã phải giải quyết bằng cách thêm một cơ chế "force start" — nếu gặp dòng nội dung có ý nghĩa mà chưa thấy separator, hệ thống sẽ tự động chuyển sang chế độ parse content. Thực tế cho thấy preprocessing chiếm 80% công sức để có 20% kết quả tốt.

---

## 4. Phân tích một câu hỏi trong scorecard (150-200 từ)

**Câu hỏi:** SLA xử lý ticket P1 là bao lâu? (ID: q01)

**Phân tích:**
- **Baseline:** Nếu sử dụng script cũ, câu hỏi này có nguy cơ trả lời sai hoặc không tìm thấy nguồn (Score: 0). Lý do là nguồn tài liệu `support/sla-p1-2026.pdf` định dạng PDF không được script cũ quét tới, và nếu chuyển sang text đơn thuần, tiêu đề "SLA TICKET - QUY ĐỊNH XỬ LÝ SỰ CỐ" cũng bị lọc mất do viết hoa toàn bộ.
- **Lỗi nằm ở:** **Indexing**. Khi dữ liệu nguồn không được nạp vào vector store hoặc nạp thiếu tiêu đề, retrieval sẽ không thể tìm thấy đoạn text chứa từ khóa "SLA" và "P1" một cách chính xác nhất.
- **Variant:** Sau khi tôi cập nhật `index.py`, variant này trả lời hoàn toàn chính xác. Hệ thống nạp được file PDF, giữ lại tiêu đề để tăng trọng số tìm kiếm theo ngữ cảnh. Chunk đầu tiên của file này giờ đây chứa đầy đủ từ khóa "SLA TICKET" và metadata "Department: IT", dẫn đến việc retrieval trả về kết quả top-1 chính xác là đoạn quy định 15 phút phản hồi và 4 giờ xử lý. Việc cải thiện indexing đã khắc phục triệt để lỗi từ gốc rễ.

---

## 5. Nếu có thêm thời gian, tôi sẽ làm gì? (50-100 từ)

Nếu có thêm thời gian, tôi sẽ thử nghiệm **Hybrid Search (Vector + Keyword)**. Kết quả bước đầu cho thấy vector search đôi khi bị nhiễu bởi các từ ngữ thông dụng. Tôi muốn kết hợp BM25 cho các từ khóa chuyên môn như mã lỗi (ví dụ: `ERR-403-AUTH`) hoặc tên bộ phận. Việc kết hợp này sẽ giúp tăng độ chính xác (Precision) của Retrieval, đặc biệt là với các câu hỏi có thuật ngữ kỹ thuật đặc thù mà mô hình embedding có thể chưa hiểu sâu.

---

*Lưu file này với tên: `reports/individual/Trinh_Dac_Phu.md`*
