# Scorecard: baseline_dense
Generated: 2026-04-13 16:14

## Summary

| Metric | Average Score |
|--------|--------------|
| Faithfulness | 3.60/5 |
| Relevance | 4.00/5 |
| Context Recall | 5.00/5 |
| Completeness | 4.20/5 |

## Per-Question Results

| ID | Category | Faithful | Relevant | Recall | Complete | Notes |
|----|----------|----------|----------|--------|----------|-------|
| q01 | SLA | 5 | 5 | 5 | 5 | Every claim in the answer is directly supported by the retri |
| q02 | Refund | 5 | 5 | 5 | 5 | Every claim in the answer is directly supported by the retri |
| q03 | Access Control | 2 | 5 | 5 | 5 | The answer mentions Level 3 access and required approvals, w |
| q04 | Refund | 5 | 5 | 5 | 3 | Every claim in the answer is directly supported by the retri |
| q05 | IT Helpdesk | 3 | 5 | 5 | 5 | The answer about account locking and unlocking is mostly gro |
| q06 | SLA | 2 | 5 | 5 | 5 | The answer incorrectly states that escalation occurs after 1 |
| q07 | Access Control | 5 | 1 | 5 | 1 | The answer accurately states that information about the Appr |
| q08 | HR Policy | 5 | 5 | 5 | 5 | Every claim in the answer is directly supported by the retri |
| q09 | Insufficient Context | 1 | 1 | 5 | 4 | The answer does not reference any information from the retri |
| q10 | Refund | 3 | 3 | 5 | 4 | The answer correctly identifies that information about the e |

## Answers

### [q01] SLA xử lý ticket P1 là bao lâu?
**Answer:** SLA xử lý ticket P1 là 4 giờ để khắc phục và 15 phút để phản hồi ban đầu kể từ khi ticket được tạo [1].

**Expected:** Ticket P1 có SLA phản hồi ban đầu 15 phút và thời gian xử lý (resolution) là 4 giờ.

---

### [q02] Khách hàng có thể yêu cầu hoàn tiền trong bao nhiêu ngày?
**Answer:** Khách hàng có thể yêu cầu hoàn tiền trong vòng 7 ngày làm việc kể từ thời điểm xác nhận đơn hàng [1].

**Expected:** Khách hàng có thể yêu cầu hoàn tiền trong vòng 7 ngày làm việc kể từ thời điểm xác nhận đơn hàng.

---

### [q03] Ai phải phê duyệt để cấp quyền Level 3?
**Answer:** Để cấp quyền Level 3, cần có sự phê duyệt của Line Manager, IT Admin và IT Security [2].

**Expected:** Level 3 (Elevated Access) cần phê duyệt từ Line Manager, IT Admin, và IT Security.

---

### [q04] Sản phẩm kỹ thuật số có được hoàn tiền không?
**Answer:** Sản phẩm kỹ thuật số không được hoàn tiền, trừ khi có lỗi do nhà sản xuất và đáp ứng các điều kiện khác. [1]

**Expected:** Không. Theo chính sách hoàn tiền, sản phẩm thuộc danh mục hàng kỹ thuật số (license key, subscription) là ngoại lệ không được hoàn tiền.

---

### [q05] Tài khoản bị khóa sau bao nhiêu lần đăng nhập sai?
**Answer:** Tài khoản bị khóa sau 5 lần đăng nhập sai liên tiếp. Để mở khóa, bạn cần liên hệ IT Helpdesk hoặc tự reset qua portal SSO [1].

**Expected:** Tài khoản bị khóa sau 5 lần đăng nhập sai liên tiếp.

---

### [q06] Escalation trong sự cố P1 diễn ra như thế nào?
**Answer:** Trong sự cố P1, quy trình escalation diễn ra như sau: nếu không có phản hồi trong 10 phút kể từ khi ticket được tạo, ticket sẽ tự động được escalate lên Senior Engineer. Ngoài ra, thông báo cho stakeholder sẽ được thực hiện ngay khi nhận ticket và cập nhật mỗi 30 phút cho đến khi sự cố được giải quyết [3].

**Expected:** Ticket P1 tự động escalate lên Senior Engineer nếu không có phản hồi trong 10 phút sau khi tạo ticket.

---

### [q07] Approval Matrix để cấp quyền hệ thống là tài liệu nào?
**Answer:** Thông tin về Approval Matrix để cấp quyền hệ thống không có trong các tài liệu được cung cấp.

**Expected:** Tài liệu 'Approval Matrix for System Access' hiện tại có tên mới là 'Access Control SOP' (access-control-sop.md).

---

### [q08] Nhân viên được làm remote tối đa mấy ngày mỗi tuần?
**Answer:** Nhân viên được làm remote tối đa 2 ngày mỗi tuần sau khi hoàn thành probation period, và lịch remote phải được Team Lead phê duyệt qua HR Portal [1].

**Expected:** Nhân viên sau probation period có thể làm remote tối đa 2 ngày/tuần, với điều kiện được Team Lead phê duyệt.

---

### [q09] ERR-403-AUTH là lỗi gì và cách xử lý?
**Answer:** Thông tin về lỗi ERR-403-AUTH và cách xử lý không có trong các tài liệu được cung cấp.

**Expected:** Không tìm thấy thông tin về ERR-403-AUTH trong tài liệu hiện có. Đây có thể là lỗi liên quan đến xác thực (authentication), hãy liên hệ IT Helpdesk.

---

### [q10] Nếu cần hoàn tiền khẩn cấp cho khách hàng VIP, quy trình có khác không?
**Answer:** Thông tin về quy trình hoàn tiền khẩn cấp cho khách hàng VIP không có trong tài liệu đã cung cấp.

**Expected:** Tài liệu chính sách hoàn tiền không đề cập đến quy trình đặc biệt cho khách hàng VIP. Theo chính sách hiện hành, tất cả yêu cầu hoàn tiền đều theo cùng quy trình tiêu chuẩn trong 3-5 ngày làm việc.

---

