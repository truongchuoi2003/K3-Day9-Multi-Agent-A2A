# Member Role Report — Day 9: Multi Agent A2A

## 1. Thông tin cá nhân

| Thông tin | Nội dung |
| --- | --- |
| Họ và tên | Quách Xuân Trường |
| MSSV | 01371 |
| Khóa/Lớp | K3 |
| Vai trò chính | Verification, QA & Submission Engineer |
| Ngày hoàn thành | 2026-08-05 |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao | Trạng thái |
| --- | --- | --- | --- | --- |
| Output validation | `src/agents/verifier.py`, `src/schemas.py` | draft output và source CSV | error list hoặc approval | Hoàn thành |
| Release QA | `architecture.md`, `logging/metadata.json`, trace/output/ZIP checks | artifacts chạy batch | checklist nộp bài | Hoàn thành |

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động | Thành viên/module được hỗ trợ | Kết quả |
| --- | --- | --- |
| Kiểm tra integration | Coordinator và Policy modules | Xác nhận output chỉ được ghi sau verification |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao | Cách xác minh |
| --- | --- | --- | --- |
| Xác thực schema và source IDs | `src/agents/verifier.py` | Danh sách lỗi chi tiết hoặc `[]` | Verifier duyệt 50 output cuối |
| Kiểm tra artifact nộp bài | `output/`, `logging/trace.jsonl`, `output.zip` | 50 output valid, ZIP đúng phạm vi | Đếm file/trace và mở archive |

Artifact cụ thể: `output.zip` chứa đúng 50 `EC_001.json`–`EC_050.json`; không có `.env`, source hay logging files.

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Một output có thể đúng syntax JSON nhưng sai source ID, sai evidence, sai refund hoặc có entity quá giới hạn. Cần checkpoint độc lập để chặn những lỗi này trước khi ghi file nộp.

### Cách triển khai

Verifier nhận draft output cùng expected case/order ID từ Coordinator. Agent xác minh order, item, payment và seller IDs bằng `DataLoader`; kiểm tra evidence chỉ có năm prefix README cho phép; đối chiếu financial totals với CSV; kiểm tra rounding, refund, action và party theo primary issue. Verifier cũng kiểm tra giới hạn schema. Nếu list errors khác rỗng, Coordinator raise `VerificationError` và không ghi JSON. QA cuối kiểm tra 50 tên output, JSON parse, 50 trace lines, metadata, architecture, Git và nội dung ZIP.

### Input, output và contract

| Thành phần | Mô tả |
| --- | --- |
| Input | Draft `CaseOutput`, expected case ID/order ID, CSV source tables |
| Output | `list[str]`; `[]` nghĩa là approved |
| Module phụ thuộc | `DataLoader`, `schemas.py`, policy conventions |
| Module sử dụng output | Coordinator output writer |
| Điều kiện lỗi cần xử lý | ID không tồn tại, evidence sai prefix, money sai, party sai, limit vượt ngưỡng |

### Cách xác minh

```bash
python -m src.main
```

- **Kết quả mong đợi:** 50 case chỉ được ghi khi Verifier pass.
- **Kết quả thực tế:** 50/50 output hợp lệ; trace có `verification: passed`.
- **Artifact/log:** `logging/trace.jsonl`, `output.zip`.

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Có thể chỉ validate JSON schema hoặc đối chiếu cả output với CSV/policy.
- **Các phương án đã cân nhắc:** JSON parse đơn thuần; hoặc validation source-grounded toàn diện.
- **Phương án đã chọn:** Verifier đối chiếu lại dữ liệu nguồn và quy tắc policy, không tin hoàn toàn Coordinator hoặc model audit.
- **Lý do:** Evidence/financial sai vẫn có thể là JSON hợp lệ nhưng bị chấm false positive hoặc hard gate.
- **Bằng chứng quyết định phù hợp:** Verifier từ chối evidence thử nghiệm `tracking:invented`; 50 output cuối pass.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi nguyên văn:** Evidence `tracking:invented` không thuộc format được README cho phép.
- **Lệnh hoặc bước tái hiện:** Thay một evidence hợp lệ bằng `tracking:invented`, gọi `VerifierAgent.verify`.
- **Nguyên nhân gốc:** Evidence không thể dựng trực tiếp từ bảng CSV và không thuộc whitelist prefix.
- **Cách xử lý:** Verifier từ chối mọi evidence kind ngoài `order`, `item`, `payment`, `seller`, `policy`.
- **Cách xác minh sau khi sửa:** Test xác nhận Verifier chấp nhận output hợp lệ và trả lỗi với `tracking:invented`.
- **Điều học được:** Validation cần kiểm tra semantic provenance, không chỉ parse string.

## 7. Hiểu biết về luồng end-to-end

Mẫu Crossref/vector index là nội dung không khớp với lab này. Luồng Day 9 được hiểu như sau:

1. Case input xác định order để các specialist truy xuất facts từ Olist CSV.
2. Payment, Delivery và Policy tạo financial/cause/resolution có thể kiểm chứng.
3. Coordinator lưu handoffs, trong đó GPT-4o mini audit trace-only và không thay thế Verifier.
4. Verifier đối chiếu output với source data và chặn output lỗi.
5. QA xác nhận 50 JSON, 50 trace records, metadata/architecture, Git commit và ZIP chỉ chứa output.

## 8. Cam kết của thành viên

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Tôi không ghi “đã chạy thành công” cho phần chưa được kiểm chứng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo này không phải bản sao nguyên văn của báo cáo thành viên khác.

**Họ và tên:** Quách Xuân Trường
**Ngày xác nhận:** 2026-08-05
