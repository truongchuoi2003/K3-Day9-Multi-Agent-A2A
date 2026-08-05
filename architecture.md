# Architecture — Multi-Agent E-commerce Dispute Resolution

## 1. Mục tiêu và nguyên tắc vận hành

Hệ thống xử lý độc lập từng case `EC_001`–`EC_050` bằng cách đối chiếu dữ liệu Olist và tạo đúng một file JSON tương ứng trong `output/`. Kiến trúc ưu tiên **bằng chứng có thể kiểm tra từ CSV**: không agent nào được kết luận chỉ từ nội dung khiếu nại, cũng không được suy diễn refund, tracking, giao thiếu/sai hoặc giao dịch không có trong dữ liệu.

Các nguyên tắc bắt buộc:

1. `claimed_order_id` là khóa khởi đầu duy nhất của case.
2. Agent chuyên trách chỉ trả về facts/evidence thuộc domain của mình; không tự ghi output cuối.
3. Coordinator chỉ tổng hợp các handoff đã có. Policy Agent là nơi duy nhất chọn `primary_issue`, trách nhiệm, refund và action.
4. Verifier là cổng bắt buộc trước khi ghi file. Nếu schema, ID hoặc số tiền không hợp lệ, case phải bị từ chối ghi và trả về lỗi có thể sửa.
5. Tất cả timestamp so sánh trực tiếp theo giá trị CSV; không chuyển múi giờ. Tất cả giá trị BRL được làm tròn 2 chữ số.
6. Mỗi lần chạy phải tạo trace mới hoàn toàn, không append trace từ lần chạy trước.

## 2. Sơ đồ luồng

```text
input/EC_xxx.json
       |
       v
+-------------------+
| Coordinator Agent |
+-------------------+
       |
       +---------------------+----------------------+------------------+
       v                     v                      v                  v
+------------------+  +----------------+  +----------------+  +----------------+
| Order & Seller   |  | Payment Agent  |  | Delivery Agent |  | Evidence Agent |
| Agent            |  |                |  |                |  | (deterministic)|
+------------------+  +----------------+  +----------------+  +----------------+
       \                     |                      /                  /
        \____________________|_____________________/__________________/
                                   |
                                   v
                          +----------------+
                          | Policy Agent   |
                          +----------------+
                                   |
                                   v
                          +----------------+
                          | Verifier Agent |
                          +----------------+
                              |          |
                         valid|          |invalid
                              v          v
                    output/EC_xxx.json  structured error -> Coordinator -> repair
```

`Evidence Agent` có thể là hàm deterministic dùng để xây evidence ID từ facts đã xác minh; không được tạo ID tự do bằng LLM. Các agent domain có thể chạy song song sau khi Coordinator xác nhận order tồn tại.

## 3. Vai trò, quyền truy cập và đầu ra

| Thành phần                   | Chỉ đọc                                                 | Không được làm                                                                   | Handoff bắt buộc                                                                                        |
| ------------------------------ | ---------------------------------------------------------- | ------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------- |
| **Coordinator Agent**    | Input case, mọi payload agent, trạng thái chạy         | Không tự thay facts CSV; không quyết định policy khi thiếu handoff             | `case_context`, payload tổng hợp, yêu cầu repair nếu verifier lỗi                                 |
| **Order & Seller Agent** | `orders`, `order_items`, `sellers`                   | Không tính refund hay kết luận giao trễ logistics                                | order status, item/seller IDs, shipping limits, item và freight totals                                   |
| **Payment Agent**        | `order_payments`, item/freight totals từ Order & Seller | Không kết luận seller/logistics                                                    | payment rows, payment total, số payment rows, reconciliation với item + freight                         |
| **Delivery Agent**       | `orders`, shipping limits theo item từ Order & Seller   | Không tự xác định refund                                                         | delivered-carrier/customer/estimated timestamps, trạng thái giao trễ, seller handoff theo từng seller |
| **Policy Agent**         | Payload đã xác minh của 3 agent domain                 | Không đọc/đoán thêm dữ liệu ngoài payload; không bỏ qua thứ tự ưu tiên | assessment, root cause, responsible parties, resolution tài chính và actions                           |
| **Evidence Agent**       | Payload đã xác minh, policy decision                    | Không sinh ID không có trong facts hoặc vượt format                             | evidence IDs và affected entities đã chuẩn hóa                                                       |
| **Verifier Agent**       | Candidate output và facts đã xác minh                  | Không “tự sửa im lặng” kết luận policy                                        | `valid` hoặc danh sách lỗi theo field                                                                |
| **Writer**               | Output đã`valid`                                       | Không ghi candidate chưa qua verifier                                               | JSON UTF-8, một file đúng tên case                                                                    |

Chỉ các file CSV là nguồn dữ liệu nghiệp vụ. `customers`, `products`, `reviews`, `geolocation` không cần trong policy hiện tại; chúng không được dùng để thay đổi kết luận nếu không có yêu cầu mới.

## 4. Contract handoff

Mọi handoff phải là JSON thuần, có `case_id`, `order_id`, `agent`, `status` (`ok` hoặc `error`) và `facts`. Giá trị không có trong CSV phải biểu diễn là `null`, không bịa giá trị thay thế.

### 4.1. Context của Coordinator

```json
{
  "case_id": "EC_001",
  "order_id": "<claimed_order_id>",
  "policy_version": "EC_POLICY_V1",
  "customer_message": "<message>",
  "opened_at": "<ISO-8601 input>"
}
```

Nếu không tìm thấy `order_id` trong `orders`, Coordinator tạo trace lỗi và không được suy diễn kết quả. Đây là dữ liệu bất thường cần được báo rõ thay vì tạo output sai.

### 4.2. Order & Seller facts

```json
{
  "order_status": "delivered",
  "items": [
    {
      "order_item_id": 1,
      "seller_id": "<seller_id>",
      "shipping_limit_date": "<timestamp>",
      "price": 100.0,
      "freight_value": 15.0
    }
  ],
  "item_total_brl": 100.0,
  "freight_total_brl": 15.0
}
```

`item_total_brl = sum(price)` và `freight_total_brl = sum(freight_value)` trên toàn bộ item của order. Nếu order không có item, hai tổng bằng `0.0`, `items` rỗng; đây không phải lý do để tự tạo seller ID.

### 4.3. Payment facts

```json
{
  "payments": [
    { "payment_sequential": 1, "payment_value": 115.0 }
  ],
  "payment_total_brl": 115.0,
  "payment_row_count": 1,
  "expected_order_total_brl": 115.0,
  "is_reconciled_within_010_brl": true
}
```

`payment_total_brl = sum(payment_value)`. Một order chỉ thỏa điều kiện split payment khi `payment_row_count >= 2` **và** `abs(payment_total_brl - expected_order_total_brl) <= 0.10`.

### 4.4. Delivery facts

```json
{
  "order_delivered_carrier_date": "<timestamp-or-null>",
  "order_delivered_customer_date": "<timestamp-or-null>",
  "order_estimated_delivery_date": "<timestamp-or-null>",
  "is_delivered_late": true,
  "seller_handoffs": [
    { "seller_id": "<seller_id>", "handoff_after_limit": true }
  ]
}
```

`is_delivered_late` chỉ true khi `order_delivered_customer_date > order_estimated_delivery_date`. Với seller `S`, `handoff_after_limit` chỉ true khi có item của `S` mà `order_delivered_carrier_date > shipping_limit_date` của item đó. Không có timestamp cần thiết nghĩa là không đủ evidence để gắn nguyên nhân giao trễ.

## 5. Policy EC_POLICY_V1

Policy Agent áp dụng quy tắc theo đúng thứ tự sau; rule đầu tiên khớp là quyết định cuối cùng:

| Ưu tiên | Điều kiện                                                 | `primary_issue`           | Root cause                           | Trách nhiệm                              | Refund / action                          |
| --------: | ------------------------------------------------------------ | --------------------------- | ------------------------------------ | ------------------------------------------ | ---------------------------------------- |
|         1 | `order_status = canceled` và `payment_total_brl > 0`    | `canceled_order_paid`     | `ORDER_CANCELED_AFTER_PAYMENT`     | `platform: OLIST_PLATFORM`               | toàn bộ payment /`issue_full_refund` |
|         2 | `order_status = unavailable` và `payment_total_brl > 0` | `unavailable_order_paid`  | `ORDER_UNAVAILABLE_AFTER_PAYMENT`  | `platform: OLIST_PLATFORM`               | toàn bộ payment /`issue_full_refund` |
|         3 | giao trễ và có seller`handoff_after_limit = true`       | `late_delivery_seller`    | `SELLER_HANDOFF_AFTER_LIMIT`       | seller vi phạm                            | toàn bộ freight /`refund_freight`    |
|         4 | giao trễ và seller không bàn giao muộn                  | `late_delivery_logistics` | `CARRIER_DELIVERED_AFTER_ESTIMATE` | `logistics_provider: LOGISTICS_PROVIDER` | toàn bộ freight /`refund_freight`    |
|         5 | ít nhất 2 payment rows và payment reconciled              | `valid_split_payment`     | `MULTIPLE_PAYMENTS_RECONCILED`     | không có                                 | 0 /`explain_valid_split_payment`       |
|         6 | không giao trễ và payment reconciled                      | `unsupported_late_claim`  | `DELIVERY_WITHIN_ESTIMATE`         | không có                                 | 0 /`reject_late_refund`                |

Case ở ưu tiên 1–4 có `case_status: "action_required"`; ưu tiên 5–6 có `case_status: "no_action"`. Không thêm cause hoặc responsible party không phục vụ rule đã chọn.

## 6. Quy tắc tạo output và evidence

`affected_entities` phản ánh các row thực tế đã dùng: order ID, tối đa 5 item (`<order_id>:<order_item_id>`), seller và payment (`<order_id>:<payment_sequential>`). Với order không có item, `item_ids` và `seller_ids` phải là `[]`.

Evidence chỉ được lấy từ các format sau:

```text
order:<order_id>
item:<order_id>:<order_item_id>
payment:<order_id>:<payment_sequential>
seller:<seller_id>
policy:<root_cause_code>
```

Candidate output bắt buộc có các nhóm field của README: `case_id`, `assessment`, `affected_entities`, `root_cause_analysis`, `evidence_ids`, `financial_resolution`, `resolution_actions`.

## 7. Verifier checklist và điều kiện ghi file

Verifier phải kiểm tra toàn bộ mục sau trước khi Writer chạy:

1. Tên output khớp input và `case_id` khớp payload.
2. Tất cả enum (`primary_issue`, `case_status`, cause code, party type, action) thuộc policy hợp lệ.
3. `confidence` trong `[0, 1]`; số tiền là number BRL làm tròn 2 chữ số; `currency = "BRL"`.
4. `item_total_brl`, `freight_total_brl`, `payment_total_brl` đúng với aggregate CSV; `recommended_refund_brl` đúng rule được chọn.
5. Mỗi order/item/seller/payment/evidence ID tồn tại, đúng format và đúng order đang xử lý.
6. `policy:<cause_code>` khớp ranked cause hạng 1; party/action/case status phù hợp policy.
7. Không vượt giới hạn: 5 ID mỗi entity set, 10 evidence, 3 causes, 3 responsible parties, 5 actions.
8. Không có field thừa cần thiết, không `NaN`, không `Infinity`, không `null` ở field output bắt buộc.

Chỉ khi toàn bộ checklist pass, Writer mới tạo `output/EC_xxx.json`. Verifier trả lỗi theo field (ví dụ `financial_resolution.payment_total_brl: aggregate mismatch`) để Coordinator chạy lại đúng agent liên quan.

## 8. Trace, metadata và khả năng tái lập

Mỗi case phải có các event trace tối thiểu: `case_started`, `order_seller_completed`, `payment_completed`, `delivery_completed`, `policy_decided`, `verification_completed`, `output_written` hoặc `case_failed`. Mỗi dòng trace có timestamp, case ID, agent, trạng thái và summary facts; tuyệt đối không ghi API key/secret.

`metadata.json` phải công khai model name, parameter size (không quá 10B cho mỗi agent), framework, runtime, policy version và thời điểm chạy. Đường dẫn chuẩn hóa cần được thống nhất trước khi nộp: README yêu cầu `trace.jsonl` và `metadata.json` ở root trong khi repo hiện có bản trong `logging/`; pipeline nên ghi vị trí mà nhóm chọn và cập nhật README nếu có thay đổi.

## 9. Luồng xử lý một case

1. Coordinator đọc và validate input, tạo `case_context`.
2. Order & Seller Agent tra `orders`, `order_items`, `sellers`; Delivery Agent nhận shipping limits; Payment Agent nhận item/freight totals.
3. Ba agent domain hoàn tất facts; Evidence Agent chuẩn hóa affected entities/evidence hợp lệ.
4. Policy Agent chọn đúng rule ưu tiên đầu tiên khớp và tạo candidate output.
5. Verifier đối chiếu candidate với facts/CSV. Nếu fail, Coordinator chỉ gửi yêu cầu sửa đến agent có trách nhiệm; nếu pass, Writer ghi JSON.
6. Sau 50 case, chạy batch verifier một lần nữa để bảo đảm có đúng 50 file, không file lạ và mọi JSON parse được, rồi tạo trace/metadata của lần chạy đó.
