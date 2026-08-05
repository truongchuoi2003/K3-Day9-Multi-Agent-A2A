# Member Role Report — Day 9: Multi Agent A2A

## 1. Thông tin cá nhân

| Thông tin | Nội dung |
| --- | --- |
| Họ và tên | Nguyễn Thị Hoàng Yến |
| MSSV | 01959 |
| Khóa/Lớp | K3 |
| Vai trò chính | Data, Order & Delivery Specialist |
| Ngày hoàn thành | 2026-08-05 |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao | Trạng thái |
| --- | --- | --- | --- | --- |
| Data access | `src/data_loader.py`, `DataLoader` | 9 CSV trong `data/` | Query helpers cho order, item, payment, seller | Hoàn thành |
| Order & delivery facts | `src/agents/order_seller.py`, `src/agents/delivery.py` | `order_id`, `OrderSellerResult` | `OrderSellerResult`, `DeliveryResult` | Hoàn thành |

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động | Thành viên/module được hỗ trợ | Kết quả |
| --- | --- | --- |
| Kiểm tra timestamp và item ID | Payment/Policy modules | Handoff dùng timestamp chuẩn hóa và ID item nhất quán |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao | Cách xác minh |
| --- | --- | --- | --- |
| Nạp và truy vấn dữ liệu Olist | `src/data_loader.py` | Nạp core tables và lazy-load supporting tables | Khởi tạo `DataLoader('data')` thành công |
| Xác định delivery và handoff trễ | `src/agents/delivery.py` | `is_late`, `seller_handoff_late`, seller/item vi phạm | Chạy `EC_001` cho kết quả seller handoff trễ |

Artifact cụ thể: handoff `DeliveryResult` của `EC_001` xác định `is_late = true`, seller vi phạm và item ID `e2a03ccf5ea816036608b2d8c3ab8e60:1`.

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Policy cần phân biệt giao trễ do seller với giao trễ do logistics. Điều này không thể suy ra từ lời khiếu nại mà phải so sánh timestamp trong `orders` và `order_items`.

### Cách triển khai

`DataLoader` nạp ngay `orders`, `order_items`, `order_payments`, `sellers`; năm bảng hỗ trợ được lazy-load để không tốn bộ nhớ khi không dùng. Các cột thời gian được parse khi đọc CSV. `OrderSellerAgent` lấy một order và tất cả item của order, tạo item ID theo format `<order_id>:<order_item_id>`. `DeliveryAgent` so sánh `order_delivered_customer_date` với `order_estimated_delivery_date`; đồng thời kiểm tra từng item bằng điều kiện carrier date lớn hơn shipping limit date. Agent giữ danh sách seller/item vi phạm để không gán trách nhiệm cho seller không vi phạm.

### Input, output và contract

| Thành phần | Mô tả |
| --- | --- |
| Input | `order_id` từ Coordinator; order và item rows từ CSV |
| Output | `OrderSellerResult` và `DeliveryResult` |
| Module phụ thuộc | `src/data_loader.py`, `src/schemas.py` |
| Module sử dụng output | Payment Agent, Policy Agent, Coordinator, Verifier |
| Điều kiện lỗi cần xử lý | Order không tồn tại, seller không tồn tại, timestamp thiếu/`NaT` |

### Cách xác minh

```bash
python -m src.main --case-id EC_001 --show-handoffs
```

- **Kết quả mong đợi:** Có order facts, item facts và delivery flags đúng dữ liệu CSV.
- **Kết quả thực tế:** `EC_001` được phân loại delivery late và seller handoff late.
- **Artifact/log:** `logging/trace.jsonl`.

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Một số order có timestamp thiếu; so sánh thiếu kiểm soát có thể tạo kết luận trễ sai.
- **Các phương án đã cân nhắc:** Coi timestamp thiếu là đúng hạn; coi là trễ; hoặc giữ trạng thái không xác định.
- **Phương án đã chọn:** Chuyển timestamp thiếu thành `None` và không suy diễn delivery/handoff đúng hạn hoặc trễ.
- **Lý do:** Chỉ kết luận từ bằng chứng CSV có thể kiểm chứng.
- **Bằng chứng quyết định phù hợp:** Policy chỉ xử lý logistics khi `seller_handoff_within_limit` được xác lập từ timestamp hợp lệ.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi nguyên văn:** So sánh pandas `NaT` với timestamp có thể cho kết quả không xác định.
- **Lệnh hoặc bước tái hiện:** Chạy agent trên order có `order_delivered_carrier_date` hoặc `shipping_limit_date` thiếu.
- **Nguyên nhân gốc:** Giá trị datetime thiếu trong pandas không tương đương `None`.
- **Cách xử lý:** Chuẩn hóa `NaT` thành `None` tại Order & Seller Agent; Delivery Agent chỉ so sánh khi hai vế đều tồn tại.
- **Cách xác minh sau khi sửa:** Chạy toàn bộ `python -m src.main`; 50 case pass Verifier.
- **Điều học được:** Dữ liệu thời gian cần được chuẩn hóa trước khi dùng làm điều kiện nghiệp vụ.

## 7. Hiểu biết về luồng end-to-end

Mẫu câu hỏi trong template đề cập Crossref/vector index, không phù hợp với Day 9. Luồng thực tế của bài này là:

1. Coordinator đọc input case, lấy `claimed_order_id` và truy vấn dữ liệu Olist.
2. Order & Seller, Payment và Delivery Agent tạo handoff facts theo từng domain.
3. Policy Agent áp dụng `EC_POLICY_V1`; GPT-4o mini tạo structured audit trong trace nhưng không thay đổi quyết định.
4. Verifier kiểm tra ID, evidence, tiền, policy và schema trước khi ghi output.
5. Thành công được xác minh bởi 50 JSON hợp lệ, 50 trace records và ZIP chỉ chứa output.

## 8. Cam kết của thành viên

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Tôi không ghi “đã chạy thành công” cho phần chưa được kiểm chứng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo này không phải bản sao nguyên văn của báo cáo thành viên khác.

**Họ và tên:** Nguyễn Thị Hoàng Yến
**Ngày xác nhận:** 2026-08-05
