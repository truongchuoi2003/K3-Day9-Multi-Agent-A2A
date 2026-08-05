# Member Role Report — Day 9: Multi Agent A2A

## 1. Thông tin cá nhân

| Thông tin | Nội dung |
| --- | --- |
| Họ và tên | Ngô Thị Hằng |
| MSSV | 01365 |
| Khóa/Lớp | K3 |
| Vai trò chính | Financial Resolution & Policy Specialist |
| Ngày hoàn thành | 2026-08-05 |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao | Trạng thái |
| --- | --- | --- | --- | --- |
| Payment reconciliation | `src/agents/payment.py` | `order_id`, item facts | `PaymentResult` | Hoàn thành |
| Policy và evidence | `src/agents/policy.py`, `src/evidence.py` | order/payment/delivery facts | `PolicyResult`, evidence IDs | Hoàn thành |

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động | Thành viên/module được hỗ trợ | Kết quả |
| --- | --- | --- |
| Rà soát financial output | Verifier module | Quy tắc refund khớp policy và các trường tiền nguồn |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao | Cách xác minh |
| --- | --- | --- | --- |
| Đối soát thanh toán | `PaymentAgent.analyze` | Tổng item, freight, payment và split-payment flag | Đối chiếu `EC_001`: 119.90 + 12.04 = 131.94 |
| Áp dụng policy theo ưu tiên | `PolicyAgent.decide` | Issue, cause, party, refund, action | Chạy 50 case không có lỗi phân loại |

Artifact cụ thể: `PaymentResult` của `EC_001` có `payment_matches = true`, `payment_total_brl = 131.94`, và payment evidence đúng format.

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Hệ thống phải hoàn tiền đúng số tiền và đúng bên chịu trách nhiệm. Một order có thể có nhiều item, nhiều payment row và split payment.

### Cách triển khai

Payment Agent tính `item_total_brl` từ `price`, `freight_total_brl` từ `freight_value`, và `payment_total_brl` từ tổng `payment_value`. Payment khớp khi sai số với item + freight không vượt 0.10 BRL. Policy Agent dùng chuỗi `if/elif` theo đúng thứ tự README: canceled, unavailable, late seller, late logistics, split payment, unsupported claim. EvidenceBuilder chỉ sinh năm loại evidence được phép, ưu tiên item vi phạm và giới hạn 10 ID.

### Input, output và contract

| Thành phần | Mô tả |
| --- | --- |
| Input | `OrderSellerResult`, `PaymentResult`, `DeliveryResult` |
| Output | `PolicyResult` và evidence IDs |
| Module phụ thuộc | `src/schemas.py`, `src/data_loader.py` |
| Module sử dụng output | Coordinator và Verifier |
| Điều kiện lỗi cần xử lý | payment thiếu giá trị, root cause không hợp lệ, payment không khớp |

### Cách xác minh

```bash
python -m src.main --limit 5
```

- **Kết quả mong đợi:** Các primary issue đầu tiên bao gồm seller late, unsupported claim, canceled, split payment và unavailable.
- **Kết quả thực tế:** 5 case đầu pass; mỗi case có refund/action đúng policy.
- **Artifact/log:** `logging/trace.jsonl`, `output/EC_001.json` đến `output/EC_005.json`.

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Có thể dùng GPT để tính refund hoặc dùng logic deterministic.
- **Các phương án đã cân nhắc:** Để model tạo resolution; hoặc cố định công thức từ README.
- **Phương án đã chọn:** Tính money, primary issue, root cause và evidence bằng code deterministic; GPT-4o mini chỉ audit facts trong trace.
- **Lý do:** Money và evidence cần tái lập được từ CSV, không phụ thuộc output ngôn ngữ của model.
- **Bằng chứng quyết định phù hợp:** 50 output được Verifier đối chiếu lại tổng item/freight/payment và pass.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi nguyên văn:** Có thể nhầm `payment_installments` là giá trị thanh toán.
- **Lệnh hoặc bước tái hiện:** Đọc một order có payment nhiều installment và so sánh với item + freight.
- **Nguyên nhân gốc:** Dataset mô tả `payment_value` là số tiền của từng payment row, không phải tiền cho mỗi installment.
- **Cách xử lý:** Chỉ cộng `payment_value`; dùng `payment_sequential` để tạo payment ID.
- **Cách xác minh sau khi sửa:** `EC_001` có tổng payment 131.94 khớp 119.90 + 12.04.
- **Điều học được:** Cần phân biệt cột định danh/cấu hình thanh toán với cột giá trị tiền thực tế.

## 7. Hiểu biết về luồng end-to-end

Mẫu câu hỏi Crossref/vector index không khớp bài Day 9. Luồng e-commerce được hiểu như sau:

1. Input cung cấp `claimed_order_id`; Data Agent truy xuất order và item facts.
2. Payment Agent đối soát tiền; Delivery Agent đánh giá timestamp.
3. Policy Agent chọn một luật ưu tiên của `EC_POLICY_V1` và EvidenceBuilder tạo IDs có thể kiểm chứng.
4. Coordinator gọi GPT-4o mini tạo audit trace, sau đó Verifier kiểm tra lại draft output.
5. Output hợp lệ chỉ được ghi khi Verifier trả về danh sách lỗi rỗng.

## 8. Cam kết của thành viên

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Tôi không ghi “đã chạy thành công” cho phần chưa được kiểm chứng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo này không phải bản sao nguyên văn của báo cáo thành viên khác.

**Họ và tên:** Ngô Thị Hằng
**Ngày xác nhận:** 2026-08-05
