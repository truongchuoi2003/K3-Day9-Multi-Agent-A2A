# Member Role Report — Day 9: Multi Agent A2A

## 1. Thông tin cá nhân

| Thông tin | Nội dung |
| --- | --- |
| Họ và tên | Nguyễn Huy Hoàng |
| MSSV | 01113 |
| Khóa/Lớp | K3 |
| Vai trò chính | Multi-Agent Orchestration & Model Integration |
| Ngày hoàn thành | 2026-08-05 |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao | Trạng thái |
| --- | --- | --- | --- | --- |
| Agent orchestration | `src/agents/coordinator.py` | input case và specialist handoffs | draft output, handoff trace | Hoàn thành |
| GPT integration và batch runner | `src/llm.py`, `src/config.py`, `src/main.py` | deterministic facts, `.env` key | GPT audit, trace, 50 outputs | Hoàn thành |

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động | Thành viên/module được hỗ trợ | Kết quả |
| --- | --- | --- |
| Tích hợp contract | Tất cả specialist agents | Handoff được ghép và chạy end-to-end |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao | Cách xác minh |
| --- | --- | --- | --- |
| Điều phối six-agent pipeline | `CoordinatorAgent.resolve_case_with_handoffs` | Draft chỉ ghi sau Verifier | Chạy 50 case thành công |
| Tích hợp GPT-4o mini | `OpenAIHandoffClient.audit_case` | Structured audit `summary_vi`, `facts_consistent` | 50 trace records có `gpt4o_mini_audit` |

Artifact cụ thể: `logging/trace.jsonl` có 50 record, mỗi record ghi model `gpt-4o-mini`, handoff các agent và trạng thái verification passed.

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Cần biến sáu module độc lập thành luồng xử lý nhất quán cho 50 case, có handoff rõ ràng, model audit thật và không để output chưa verify được ghi ra đĩa.

### Cách triển khai

Coordinator lấy `claimed_order_id`, lần lượt gọi Order & Seller, Payment, Delivery và Policy Agent. Sau khi có deterministic facts, Coordinator gọi GPT-4o mini qua Chat Completions API để trả JSON audit ngắn. Prompt giới hạn model không thay đổi issue, refund, entity hay evidence. Coordinator dựng `CaseOutput`, gọi Verifier, chỉ ghi JSON khi errors rỗng. `main.py` hỗ trợ chạy một case, 5 case hoặc 50 case; trace được mở bằng mode `w` để chỉ giữ lượt mới nhất. API key được đọc runtime từ `OPENAI_API_KEY` trong `.env`, không ghi vào code hay log.

### Input, output và contract

| Thành phần | Mô tả |
| --- | --- |
| Input | Input JSON, specialist handoffs, `OPENAI_API_KEY` tại runtime |
| Output | `CaseOutput`, GPT audit trong trace, `output/EC_xxx.json` |
| Module phụ thuộc | Six agents, `src/llm.py`, `src/config.py` |
| Module sử dụng output | Verifier, người chấm, trace audit |
| Điều kiện lỗi cần xử lý | Thiếu API key, OpenAI HTTP error, model trả JSON không đúng schema, Verifier reject |

### Cách xác minh

```bash
python -m src.main --case-id EC_001 --show-handoffs
python -m src.main
```

- **Kết quả mong đợi:** GPT audit có trong trace; 50 output chỉ được ghi sau verification.
- **Kết quả thực tế:** `EC_001` và toàn bộ 50 case pass; trace có 50 `gpt4o_mini_audit`.
- **Artifact/log:** `logging/trace.jsonl`, `output.zip`.

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Giảng viên yêu cầu dùng GPT-4o mini nhưng output cần chính xác theo policy cố định.
- **Các phương án đã cân nhắc:** Để GPT sinh toàn bộ output; hoặc dùng GPT làm audit trên facts/decision deterministic.
- **Phương án đã chọn:** GPT-4o mini sinh structured audit trace-only; policy và output schema do Python agents và Verifier kiểm soát.
- **Lý do:** Vẫn có model usage thật, đồng thời giữ financial resolution và evidence tái lập từ CSV.
- **Bằng chứng quyết định phù hợp:** 50 record trace có audit model và 50 JSON pass Verifier.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi nguyên văn:** `OPENAI_API_KEY is missing; add it to .env`.
- **Lệnh hoặc bước tái hiện:** `python -m src.main --case-id EC_001 --show-handoffs` khi `.env` không có key.
- **Nguyên nhân gốc:** Runtime không tìm thấy biến `OPENAI_API_KEY`.
- **Cách xử lý:** Dùng biến `OPENAI_API_KEY` trong `.env`; client chỉ đọc key lúc chạy và `.gitignore` loại trừ `.env`.
- **Cách xác minh sau khi sửa:** `EC_001` trả `gpt4o_mini_audit` với model `gpt-4o-mini`.
- **Điều học được:** Cần tách cấu hình model trong source khỏi credential runtime trong `.env`.

## 7. Hiểu biết về luồng end-to-end

Mẫu Crossref/vector index là template không khớp bài Day 9. Luồng thực tế:

1. `main.py` chọn input cases, khởi tạo DataLoader, specialist agents, GPT client và Verifier.
2. Coordinator điều phối các handoff domain; mỗi agent có input/output contract trong `schemas.py`.
3. GPT-4o mini audit facts đã chuẩn hóa và kết quả chỉ nằm trong trace.
4. Verifier là checkpoint bắt buộc trước output writer.
5. Một run hoàn chỉnh thành công khi có 50 output JSON hợp lệ, 50 trace record pass và ZIP chỉ chứa output.

## 8. Cam kết của thành viên

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Tôi không ghi “đã chạy thành công” cho phần chưa được kiểm chứng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo này không phải bản sao nguyên văn của báo cáo thành viên khác.

**Họ và tên:** Nguyễn Huy Hoàng
**Ngày xác nhận:** 2026-08-05
