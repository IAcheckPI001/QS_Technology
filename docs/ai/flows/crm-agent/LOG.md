# Nhật ký luồng crm-agent

Nhật ký phát triển, **mục mới nhất ở trên**. Chỉ thêm mục mới, không sửa mục cũ; nếu mục
cũ sai, thêm mục mới đính chính. Sau khi thêm mục, viết lại [STATE.md](STATE.md).
Mẫu mục: [../_template/LOG.md](../_template/LOG.md).

Các mục tới 2026-11-10 (nguyên văn từ `current-state.md` và `architecture.md`):
[LOG-archive-2026-11-11.md](LOG-archive-2026-11-11.md).

## 2026-11-12 · Giới hạn gọi tool: đếm call thật chạy, trần CRM riêng của crm_query · loại: thay đổi

- Vấn đề: câu "còn 2 sale kìa… khách đầu tiên tên gì" chạm giới hạn gọi tool, câu trả lời "thử lại sau".
  - Log khớp code: hết trần riêng 4 lần của `crm_query`, nên 2 call nhận `tool_call_limit`; 2 call đó vẫn bị trừ trần chung 8, nên call thứ 3 nhận nhầm `tool_budget_exhausted`.
  - Nguồn chính: LLM tự suy username (`hieu.nguyen-sm`, `son`; thật có `@qstcnc.com`), nên query ra rỗng và gọi lại.
- Kiểm trên CRM (`POST /reports/query`):
  - đếm khách nhiều sale gộp được một query (`in` + `dimensions`);
  - "khách đầu tiên của từng sale" phải tách mỗi người một query `limit 1` (danh sách gộp bị một người che; `min` chỉ cho cột số).
  - Không nới trần (243 lượt eval không chạm trần thật).
- Thay đổi (Toma duyệt):
  - `agent/runner.py`: trần chung chỉ đếm call không bị `tool_call_limit`.
  - `tools/crm_query.py`: `max_calls_per_turn` 4 → 6 (`MAX_QUERY_ATTEMPTS_PER_TURN`, tính cả lần bị chặn); `run()` từ chối lần gửi CRM thứ 5 (`MAX_CRM_QUERIES_PER_TURN`, `QueryTurnState.crm_queries`) bằng `tool_call_limit`. Lần `rejected`/`invalid_args` không tốn lượt CRM.
- File: `agent/runner.py`, `tools/crm_query.py`, `tests/chatbot/test_agent_tool_neutrality.py` (+1), `tests/chatbot/test_crm_query_tool.py` (+1), README.
- Kiểm chứng: từ `backend/`, `pytest tests` → 1028 passed, 14 skipped; `check_ai_docs.py` đạt. Eval do Toma tự chạy.
- Ảnh hưởng contract: mã `tool_call_limit` giữ nguyên; `crm_query` có thể trả mã này khi đủ 4 lần gửi CRM. Không đổi HTTP/SSE.
- Mở tiếp: guide chưa có luật "username chỉ lấy từ kết quả tool"; câu trả lời khi chạm giới hạn.

## 2026-11-12 · Hướng Y: gpt-4.1-mini, sửa lỗi nghiệp vụ và ngày trong code, làm gọn guide · loại: thay đổi, quyết định, đánh giá

- Quyết định (Toma):
  - chọn hướng Y: `AGENT_MODEL=gpt-4.1-mini`, sửa lỗi nghiệp vụ và lỗi ngày trong code;
  - eval chỉ với gpt-4.1-mini;
  - "khách hàng" không tính spam (lost vẫn tính);
  - `support_assignments` có kỳ thì tính mọi lần giao, bỏ `is_current`.
- Thay đổi code:
  - `dates.stated_years`; `compile_raw`:
    - bỏ năm câu hỏi không nêu;
    - kỳ trong filters → `date_range` (gồm `_month eq "N"`, ghép `_year`);
    - bỏ filter lặp kỳ;
    - `DROP_WITH_DATE_RANGE`.
  - `DEFAULT_FILTERS["customers"]` loại spam; `include_inactive` dùng chung.
  - `RawFilter`: `is_null`/`not_null` bỏ qua value. `check_path` gợi ý khoá ngoại khi dùng tên bảng.
  - Bỏ enum tên bảng trong `SchemaRequest`/`RawQuery`, kiểm bằng `QUERYABLE_TABLES` kèm gợi ý `difflib`.
  - Bỏ 8 ghi chú `TABLE_NOTES` chỉ liệt kê cột. `<now>` đặt trước tool guide.
- Guide `crm_query`:
  - 2.044 → 1.525 token;
  - bỏ luật đã ép trong code (năm, "hiện tại thì lọc" cột vòng đời, rows là dữ liệu);
  - thêm: lọc thẳng theo username, gọi `crm_schema` mỗi lượt, nêu tháng/năm, không đặt lại filter mặc định.
- Eval:
  - `{staff_username}` (biến `CRM_EVAL_STAFF_USERNAME`); nới q6, f2;
  - d1 chấp nhận rỗng nhưng phải nêu 2025;
  - `date_field`/`no_date_range` xét body gửi CRM;
  - `passed_ignoring_budget`.
- Số đo (27 case × 3; [báo cáo](../../reports/crm_agent_eval_C_gpt41_2026-11-12.md)):
  - (a) sửa code: 64/81;
  - (b) gọn guide: 69/81, nhưng q3, r2 tụt và d2 trả số sai, do bỏ dòng ngày và ví dụ join tên;
  - (c) khôi phục hai dòng đó: **78/81**, 21 case cũ 60/63 (mốc sáng 38/63).
  - Token vào mỗi câu ~29,9k → 21,0k; phần cố định mỗi bước 5.868 → 4.251.
- Kiểm trên CRM: tháng 12/2025 có 0 khách; phiếu tạo tháng 10/2026 không cái nào đóng tháng 11; r1 có 3 khách theo `product_item_id.customer_id`.
- Mở tiếp:
  - "khách" của phiếu hỗ trợ: `customer_organization_id` hay chủ máy (r1);
  - đề nghị CRM sửa mô tả `is_current`;
  - đặt `AGENT_MODEL` ở môi trường thật.

## 2026-11-12 · Phân vùng lượt trượt của đợt đo lại; dữ liệu eval lỗi thời · loại: đánh giá

- Vấn đề: cần biết 25 lượt trượt mỗi model (cùng 21 case) do agent hay do bộ eval.
- Kiểm bằng `POST /reports/query`:
  - username `an` (r1, q7, q12) không tồn tại;
  - F86 có `code` = `name`;
  - `created_month` = `created_at_month`;
  - khách trừ spam/lost là 545 (agent nói 550).
- Kết quả: gpt-4o-mini 4 lượt trượt do eval, 21 do agent (năm sai, hiểu sai tham số, ngữ cảnh qua lượt, luật nghiệp vụ). gpt-4.1-mini 19 do eval (dữ liệu case 7, chấm theo cách viết 6, vượt số lần gọi 6), 6 do agent (q13 `is_current`, s1 spam/lost). Chi tiết: mục 8 của [báo cáo](../../reports/crm_agent_eval_C_2026-11-12.md).
- Mở tiếp: sửa r1, q7, q12 (username có thật); nới expect q6, f2.

## 2026-11-12 · Đo lại phương án C sau P0 và cập nhật schema CRM · loại: đánh giá

- Cấu hình: như đợt nền (`CRM_TOOLS=query`, `AGENT_MAX_STEPS=5`, token admin), 27 case `crm_query` × 3 lần (21 case cũ + d1, d2, v1–v4), gpt-4o-mini và gpt-4.1-mini. Báo cáo: [crm_agent_eval_C_2026-11-12.md](../../reports/crm_agent_eval_C_2026-11-12.md); log thô ngoài repo.
- Số đo:
  - cùng 21 case: gpt-4o-mini 37 → 38/63, gpt-4.1-mini 40 → 38/63; toàn bộ 27 case: 50/81 mỗi model;
  - token vào mỗi câu +35–39% (23.9k → 32.2k, 22.7k → 31.6k); bước LLM 3.7 → 4.1; p50 4.4s → 6.2s (gpt-4o-mini);
  - bị chặn ở dịch vụ AI 12 → 31 và 5 → 29 (chủ yếu ngày trong `filters`); rỗng và CRM 400 giảm.
- Cải thiện: v1–v4 24/24; q9 + q11 (gpt-4o-mini) 0/6 → 5/6; f1 (gpt-4.1-mini) 0/3 → 3/3.
- Nhóm lỗi còn lại:
  1. ngày (kỳ trong `filters`, LLM tự điền năm 2023/2026: d1, d2 0/12);
  2. hồi quy luật "hiện tại": `is_current` ở q13 6/6, `deleted_at` ở r3 3/3 (gpt-4o-mini), do mô tả cột mới;
  3. gọi thêm tool tra tên → vượt 4 lần gọi dù dữ liệu đúng (r2, q3);
  4. ghi chú nghiệp vụ không được áp (s1, q6).
- Mở tiếp: sửa ngày trong code (tự chuyển, thông báo kèm ngày hôm nay, chặn kỳ tương lai); giới hạn luật "hiện tại" khi có `date_range`; tra tên trong cùng query; tách chấm "dữ liệu đúng"/"ngân sách bước"; P1.

## 2026-11-12 · Đếm nhân viên theo vai trò: known_values, filter mặc định, include_inactive · loại: thay đổi, quyết định

- Vấn đề: "có bao nhiêu nhân viên sales?" với gpt-4o-mini ra 46 (3/3 lần): đếm mọi tài khoản `auth_users` đang dùng (gồm 34 tài khoản khách). Đúng theo CRM: 3 (4 kể cả tài khoản đã tắt).
- Phân tích theo bước, bằng thí nghiệm chỉ vá dòng chọn bảng của guide:
  - Bước 1 (chọn bảng): lỗi gốc do guide map "nhân viên → auth_users". Vá guide: 3/3 chọn `user_roles`. Schema/quan hệ của CRM đã đủ, không phải nguồn lỗi.
  - Bước 3 (mã vai trò): LLM đoán mã theo tiếng Anh ("kho" → `warehouse`, mã thật `KHO`).
  - Bước 4 (`is_active`): LLM bỏ qua luật lọc tài khoản còn dùng 9/9 lần dù guide và ghi chú đều nêu.
  - Bước 5–6: metric lẫn lộn; câu trả lời nói "hiện tại" khi chưa lọc.
- Quyết định/luật (Toma):
  - Vai trò do admin tạo để gom nhóm/phân quyền, ít đổi, không phải enum; một người có thể nhiều vai trò.
  - "Nhân viên sales" = người được gán vai trò sales (admin có quyền sales nhưng không tính).
  - Lọc tài khoản còn dùng: đặt mặc định trong code (không phụ thuộc model).
- Thay đổi:
  - `hints.LOOKUP_TABLES` + `CrmSchemaCache.lookup`: `crm_schema` trả `known_values` (giá trị thật của `roles` hệ thống, trạng thái/nhóm khách, lĩnh vực), cho chính bảng và khoá ngoại trỏ tới nó.
  - `hints.DEFAULT_FILTERS` + `compile_raw`: `user_roles` tự thêm `user_id.is_active eq true` khi LLM không lọc cột đó, nhãn "(mặc định: …)" trong `applied.filters`.
  - `RawQuery.include_inactive` (mới): bỏ filter mặc định. Lần thử đầu dùng "LLM tự lọc `not_null`" thì 0/3 lần làm được, và LLM còn nói sai "bao gồm cả người đã nghỉ"; tham số riêng: 3/3.
  - Guide `crm_query`: nhân viên theo vai trò → `user_roles`; không đếm `auth_users` cho số nhân viên; không tự dịch/đoán mã, dùng `known_values`; nêu điều kiện mặc định khi trả lời. Ghi chú `user_roles`, `auth_users` cập nhật.
  - Eval: case v1 (sales), v2 (kể cả đã nghỉ), v3 (kho), v4 (kế toán), id `v*_…` để không trùng tiền tố với case s1/s2 cũ; key mới `filter_equals`, `sent_filters`.
- File: `reporting/raw/{hints,schema,compile}.py`, `schemas/system/raw_query.py`, `tools/{crm_schema,crm_query}.py`, `tests/chatbot/test_crm_query_tool.py` (+6 test), `evals/{run_crm_agent_eval.py,crm_agent_cases.json}`, README, STATE.
- Kiểm chứng:
  - từ `backend/`, `pytest tests` → 1017 passed, 14 skipped;
  - eval thật gpt-4o-mini, 3 lần × {v1–v4, q4, q5}: v1–v4 12/12 (3, 4, 0, 1 khớp `POST /reports/query`), q4 3/3, q5 2/3.
- Ảnh hưởng contract/API/schema: schema tool `RawQuery` thêm `include_inactive` (OpenAI strict: bắt buộc điền); output `crm_schema` thêm `known_values`; `applied.filters` có thể chứa filter mặc định. Không đổi HTTP/SSE, mã lỗi.
- Mở tiếp:
  - q5 ("liệt kê họ tên và username"): 1/3 lần LLM lọc `user_id` trên `auth_users` → CRM 400 ba lần, chạm giới hạn 4 lần gọi; nên dùng `user_id.username` từ `user_profiles` (chưa xử lý).
  - Câu trả lời vẫn ít nêu giả định; filter mặc định và `known_values` là mầm của semantic layer (P1).

## 2026-11-12 · Cập nhật tool theo schema CRM mới (A, A', B, C1, E) · loại: thay đổi

- Vấn đề: CRM đã tự mô tả bảng/cột/quan hệ và xác nhận lưu UTC (mục đánh giá cùng ngày), nhưng tool chưa đưa các mô tả đó tới LLM và trả giờ UTC như giờ VN.
- Quyết định/luật (Toma): làm theo kế hoạch A → A' → B → C1 → E; `referenced_by` chỉ là metadata, câu hỏi "cha không có con" tách thành hai query; múi giờ theo lựa chọn (a).
- Thay đổi:
  - A: `CrmReportClient.get_table` đọc thêm mô tả cột, `cardinality`, `nullable`, `referenced_by`, `deleted_at_meaning`; `get_table_descriptions` lấy mô tả bảng từ `GET /reports/datasets`. `CrmSchemaCache` cache mô tả bảng cùng TTL (lỗi: trả rỗng, không cache). `crm_schema` trả `description`, cột kèm mô tả, quan hệ `(1-1)`/`(có thể trống)`, `referenced_by` theo CRM, `deleted_at`.
  - A': `policy.py` thêm `NOT_EXPOSED_TABLES` (`sales_users`, `user_types`) và `UNRELEASED_TABLES` (8 bảng module mới); `table_blocked` và `QUERYABLE_TABLES` dùng `UNAVAILABLE_TABLES`. Quan hệ sống trỏ tới các bảng này bị ẩn, join bị chặn.
  - B: `hints.py` bỏ `sales_users`, `user_types` và ghi chú `sales_users`; ghi chú bảng chính thêm luật `is_current`, `is_active`, "bán được" không lọc `deleted_at`, khách của phiếu là chủ hiện tại của máy. Guide `crm_query` thêm luật xoá mềm, cột vòng đời (hiện tại thì lọc, lịch sử thì không), giờ, ví dụ "khách chưa có máy"; tra nhân viên lấy kèm `user_id.is_active`. Guide `crm_report` thêm ranh giới UTC cho ba dataset dùng Reporting API.
  - C1: `render_value` đổi mọi thời điểm (kể cả chuỗi) sang `CRM_REPORT_TIMEZONE`, không kèm múi giờ coi là UTC; chuỗi chỉ có ngày giữ nguyên. Áp cho `crm_query`, `crm_records`.
  - E: case đáp án không phải số nên không cần tính lại; `r3_sold_products_october` thêm `queries_none` lọc `deleted_at`. `check_crm_query_tool.py`: sửa lỗi có sẵn (query mẫu thiếu `mode`), không tính bảng `NOT_EXPOSED`/`UNRELEASED` là lệch.
- File: `providers/crm_api.py`, `reporting/raw/{schema,policy,hints}.py`, `reporting/records.py`, `tools/{crm_schema,crm_query,crm_report}.py`, `tests/chatbot/test_crm_query_tool.py` (+3 test, CRM giả phục vụ `/reports/datasets`), `tests/chatbot/test_crm_records_tool.py` (+8 trường hợp giờ, sửa kỳ vọng giờ), `evals/{check_crm_query_tool.py,crm_agent_cases.json}`, README, STATE.
- Kiểm chứng:
  - từ `backend/`, `pytest tests` → 1011 passed, 14 skipped;
  - `npm run build` đạt; `npm run lint` 432 lỗi có sẵn ở frontend;
  - `check_crm_query_tool.py` token admin → 13 query mẫu đạt, 4 query bị chặn; còn 13 bảng index tĩnh lệch cột;
  - `crm_schema` với CRM thật, 10 bảng chính: 3.4k → 5.8k token.
- Ảnh hưởng contract/API/schema: output tool `crm_schema` thêm `description`, `deleted_at`, định dạng `columns`/`relations` thêm phần mô tả (chỉ LLM thấy); thời điểm trong rows của `crm_query`/`crm_records` có múi giờ VN thay vì chuỗi UTC. Không đổi HTTP/SSE, mã lỗi.
- Mở tiếp: cập nhật index tĩnh khi có dump mới; đo lại C (token và độ chính xác); chờ CRM thêm `timezone`.

## 2026-11-12 · Giữ nguyên `product_user_access`, `product_agents` · loại: quyết định

- Vấn đề: số liệu hai bảng chưa khớp mô tả của CRM (mục đánh giá cùng ngày bên dưới).
- Quyết định/luật (Toma): CRM chưa sửa được vì có thể ảnh hưởng logic phía CRM; tool giữ nguyên cách xử lý, không thêm luật riêng. Bỏ câu hỏi này khỏi danh sách gửi CRM.
- File: `STATE.md`.

## 2026-11-12 · Đánh giá schema CRM sau bản cập nhật mô tả; múi giờ tạm theo UTC · loại: đánh giá, quyết định

- Vấn đề: CRM cập nhật mô tả bảng/cột của Reporting API. Cần biết schema đã đủ rõ để LLM sinh query chưa.
- Kiểm (token admin, `GET /reports/datasets`, `GET /reports/tables/{t}` cho 126 bảng, vài query đếm; chỉ in số đếm):
  - Đợt 1: 126/126 bảng, 1.199/1.199 cột, 288/288 quan hệ có mô tả; cột trạng thái liệt kê giá trị.
  - Gửi CRM 4 góp ý; CRM sửa (migration 000466). Đợt 2 xác nhận:
    - API tự lọc `deleted_at IS NULL` ở bảng gốc và bảng join; dòng con có khoá ngoại bắt buộc trỏ tới cha đã xoá bị loại (`support_assignments` 46 → 25). Khoá ngoại tuỳ chọn giữ dòng con, cột của cha trống.
    - `deleted_at_meaning`: `ended` cho `product_ownerships`, `product_agents`, `product_user_access` (API không lọc), `deleted` cho 12 bảng còn lại. `product_ownerships` 177 → 136.
    - Quan hệ có `cardinality` (`many_to_one`, `one_to_one`) và `nullable`; mỗi bảng có `referenced_by`. Join vẫn chỉ đi con → cha (`customers` → `product_items.code` trả 400 `has no relation`).
    - Cột timestamp có `timezone: "UTC"`; giá trị trả về là chuỗi UTC (không offset, hoặc `+00`). `date_range` chỉ nhận `YYYY-MM-DD`; nhóm `_day/_month/_year` cắt theo UTC.
    - 11 cột vòng đời được viết lại mô tả (`is_active`, `is_current`, `merged_into_id`, `customer_hidden_at`...).
  - Lệch so với code của mình: `LiveTable` (`reporting/raw/schema.py`) bỏ mọi mô tả; `sales_users`, `user_types` vẫn trong danh sách bảng nhưng CRM không còn trả; 8 bảng mới của CRM chưa có trong index.
- Quyết định/luật (Toma):
  - Múi giờ: CRM lưu UTC, màn hình CRM hiển thị theo trình duyệt (giờ VN). Chưa có tham số múi giờ cho query, nên **tạm giữ cách gửi ngày lịch VN** (ranh giới kỳ thực tế là 07:00 giờ VN). LLM chỉ nói rõ khi câu hỏi nhắm vào một ngày hoặc khung giờ cụ thể. Đề nghị CRM thêm `timezone` cho `POST /reports/query`.
  - `auth_users.is_active`: true là đang dùng, false là không còn dùng. Tra người, danh sách nhân viên hiện tại lọc `is_active = true`; thống kê lịch sử không lọc.
  - 8 bảng mới (`goods_inspections`, `goods_inspection_items`, `material_requests`, `material_request_items`, `material_uoms`, `issue_types`, `item_categories`, `receipt_types`): CRM mới khởi tạo, chưa triển khai, chưa đưa vào tool.
- File: chỉ tài liệu (`LOG.md`, `STATE.md`). Chưa sửa code.
- Ảnh hưởng contract/API/schema: không (chưa triển khai).
- Mở tiếp:
  - Kế hoạch: A (`crm_schema` trả mô tả, cardinality, nullable, `referenced_by`, `deleted_at_meaning`), A' (bỏ `sales_users`/`user_types`, chặn rõ 8 bảng mới nếu chuyển sang lấy danh sách từ API), B (viết lại `hints.py`), C1 (đổi timestamp trả về sang giờ VN), E (tính lại đáp án eval, đo lại).
  - Hỏi CRM: `product_user_access` báo 2 dòng thu hồi nhưng đo được 16/67; `product_agents` từ 2 dòng xuống 0; `referenced_by` có hỗ trợ join ngược không; tham số `timezone`; cố định `TZ=UTC` cho container API.

## 2026-11-11 · P0: luật chung theo kiểu cột cho `crm_query` · loại: thay đổi

- Vấn đề: đợt đo nền có nhiều query sai kiểu vẫn được CRM chạy và trả 0 dòng, khiến agent khẳng định "không có dữ liệu". Ví dụ: tên trên cột uuid, kỳ thời gian nằm trong filters, năm sai.
- Quyết định/luật (Toma):
  - Hướng dài hạn là semantic layer, ghi trong kế hoạch, chưa làm.
  - Trước mắt làm P0: các luật chung suy ra từ schema, không vá theo từng case.
  - Giảm nguy cơ chặn nhầm: không chặn năm lạ; chuẩn hoá số/bool thay vì chặn; cho phép `contains "YYYY-MM"` trên cột ngày thứ hai; so enum không phân biệt hoa thường.
- Thay đổi:
  - `reporting/raw/values.py` (mới) và `compile_raw` kiểm giá trị filter theo kiểu cột cuối của đường dẫn:
    - kiểu lấy qua `ColumnType`: schema sống trong cache trước, index tĩnh sau;
    - cột ảo `*_day/_month/_year` của cột ngày coi là cột ngày.
  - `RawDateRange` thêm `preset` `month`/`year` và trường `month`, `year`. Hàm `calendar_range` tính kỳ; "tháng N" không có năm là tháng N gần nhất tính tới hôm nay.
  - Field thừa của `date_range` được ghi vào `ignored`.
  - Mode list: `order_by` theo cột chưa chọn thì cột đó được thêm vào `select` (còn chỗ), không còn bị bỏ im lặng.
  - Guide dòng "Ngày" cập nhật.
  - Eval:
    - expect `order_by`;
    - siết r2, q7;
    - f1 đổi thành "năm nay";
    - thêm d1 ("tháng 12"), d2 (hai cột ngày);
    - `compare_agent_models` thống kê "chặn theo lý do".
- File: `reporting/raw/{values,compile,policy}.py`, `reporting/dates.py`, `schemas/system/raw_query.py`, `tools/crm_query.py`, `tests/chatbot/test_crm_query_tool.py` (+25 test, gồm các dạng hợp lệ phải qua), `evals/*`.
- Kiểm chứng: từ `backend/`, `.\venv\Scripts\python.exe -m pytest tests` → 987 passed, 14 skipped. Eval thật chưa chạy lại.
- Ảnh hưởng contract/API/schema:
  - schema tool `RawQuery.date_range` thêm giá trị và field (chỉ LLM thấy);
  - lỗi mới vẫn là `tool_invalid_args`;
  - không đổi HTTP/SSE.
- Mở tiếp: đo lại cùng ma trận nền; xem lý do chặn để phát hiện chặn nhầm; sau đó lập kế hoạch P1 (semantic layer) và bổ sung đề nghị gửi CRM.

## 2026-11-11 · Đo nền phương án C, token admin · loại: đánh giá

- Cấu hình: `CRM_TOOLS=query`, `AGENT_MAX_STEPS=5` (môi trường chạy), 21 case `crm_query` × 3 lần,
  gpt-4o-mini và gpt-4.1-mini. Kết quả gốc nằm ngoài tài liệu, có dữ liệu CRM, không commit.
- Số đo:

| | gpt-4o-mini | gpt-4.1-mini |
|---|---|---|
| Đạt (theo expect) | 37/63 | 40/63 |
| Bước LLM tb; phân phối | 3.7; 3 bước 37/63 | 3.6; 3 bước 45/63 |
| crm_query: ok / rỗng / CRM 400 / chặn ở AI | 59 / 26 / 5 / 12 | 54 / 20 / 7 / 5 |
| Token vào tb mỗi câu; % cố định | 23.9k; 92% | 22.7k; 94% |
| Latency p50 / p95 | 4.4s / 12.9s | 4.2s / 9.6s |

- Nhóm lỗi chính (đọc log từng lượt):
  1. Ngày: 22/159 query lọc ngày bằng `filters` (`created_at in [...]`, `contains "2023-10"`, `created_at_year eq`) kèm `date_range` sai kỳ (`this_month` cho "tháng 10"/"tháng trước"); 15 query dùng năm 2020–2025. Kết quả rỗng, agent trả lời "không có dữ liệu".
  2. Giá trị filter sai kiểu đi thẳng tới CRM: tên hoặc chuỗi giữ chỗ trên cột uuid ("Zzyzx", "UUID của nhân viên Hiếu", chuỗi `SELECT ...`). CRM không trả 400 mà trả count 0, nên lỗi im lặng.
  3. Tra tên → UUID hai lượt: gpt-4o-mini bỏ qua (q9 0/3, q11 0/3); gpt-4.1-mini làm đúng (3/3).
  4. Ghi chú nghiệp vụ không được áp: s1 (loại spam/lost) 0/6.
  5. Quan hệ ngược (q12 user_roles) 0/6; "tháng 10" (q13) 0/6.
- Expect đang chấm lỏng: r2 đạt 6/6 dù mọi query đều rỗng vì lỗi ngày; q7 (4o-mini) đạt dù `order_by` bị bỏ và `contains "an"` khớp nhiều sale. Tỉ lệ đúng thật thấp hơn 59–63%.
- Đối chiếu giả thuyết: #1 (semantic trong prose) xác nhận; #2 (≥3 bước) xác nhận, nhưng latency p50 khoảng 4s vẫn chấp nhận được; chi phí chủ yếu là phần cố định (system prompt + định nghĩa tool, khoảng 6k token mỗi bước); #3 (mất ngữ cảnh qua lượt) chưa kết luận: f1 không hợp lệ (tháng này chỉ 2 khách mới), f2 giữ được filter nhưng hỏng vì lỗi ngày; #4, #5 chưa đo.
- Phát hiện mới: phía AI và CRM đều không kiểm kiểu giá trị filter (uuid, ngày); date_range và filter ngày không bị cấm dùng cùng nhau.
- Mở tiếp: đợt sale thường và A (catalog); sửa expect r2, q7; chọn hướng sửa.

## 2026-11-11 · Khảo sát phương án C và harness đo nền · loại: đánh giá

- Vấn đề: chưa biết C (`crm_schema` + `crm_query`) có hiệu quả không; chưa từng chạy eval thật.
  Khảo sát code đưa ra các giả thuyết, cần số đo trước khi đổi kiến trúc:
  1. Không có semantic layer: nghĩa nghiệp vụ nằm trong prose (`CRM_QUERY_GUIDE`, `TABLE_NOTES`, ~20/118 bảng có note), không test được.
  2. Tối thiểu 3 lần gọi LLM tuần tự mỗi câu (schema → query → trả lời); tra tên người 4, có lỗi 5–6.
  3. Kết quả tool không sang lượt sau (history chỉ có văn bản): "xem tiếp", "trong số đó" phải dựng lại query.
  4. Bảng ngoài `customers` cần `auth.manage_roles`: sale thường gần như chỉ dùng được `customers`.
  5. Schema hai nguồn (index tĩnh từ SQL dump và `GET /reports/tables`) có thể lệch.
  6. Tra tên → UUID, OR/so sánh do LLM làm qua nhiều bước.
  7. Guide của mọi tool được phép luôn vào system prompt; `SchemaOutput` không tự cắt (vượt `AGENT_TOOL_OUTPUT_TOKENS` thì mất cả output).
- Quyết định/luật: đo nền trước khi chọn hướng kiến trúc (duyệt: Toma). Ma trận đo: C với token
  admin (gpt-4o-mini, gpt-5-mini), C với token sale thường, A (`CRM_TOOLS=catalog`) trên case A làm được.
- Thay đổi:
  - `compare_agent_models.py`: `--json` (số đo theo model × case × lần), % token cố định (system
    prompt + định nghĩa tool mỗi bước), phân phối số bước, lỗi tool theo mã, lỗi agent theo mã,
    outcome `crm_query` của mọi lượt.
  - `run_crm_agent_eval.py`: expect `offset_min`.
  - `crm_agent_cases.json`: thêm `s1` (loại spam/lost theo note), `s2` (status không có note),
    `f1`/`f2` (hỏi tiếp qua lượt).
  - Bỏ `print` debug trong `agent/runner.py` `_call_key` (in argument tool, kể cả giá trị filter, ra stdout).
- File: `evals/{compare_agent_models,run_crm_agent_eval}.py`, `evals/crm_agent_cases.json`, `agent/runner.py`.
- Kiểm chứng: từ `backend/`, `.\venv\Scripts\python.exe -m pytest tests` → 964 passed, 14 skipped;
  `report`/`write_json` chạy thử với số liệu giả. Eval thật chưa chạy.
- Ảnh hưởng contract/API/schema: không.
- Mở tiếp: chạy ma trận đo; ghi số đúng thật vào `answer_contains_all` cho 4–5 case; đối chiếu
  giả thuyết 1–7 với số đo rồi chọn hướng (semantic layer, lai A+C, sửa context).

## 2026-11-11 · Giám sát query LLM dựng cho `crm_query` · loại: thay đổi

- Vấn đề: không có cách xem query LLM dựng có đúng không. Ví dụ ca Hohmeier: query hợp lệ nhưng ra 0 dòng. Trước đây trace chỉ có hình dạng query; không thấy giá trị filter, body gửi CRM, field bị bỏ qua, argument bị validate từ chối hay chuỗi các lần sửa.
- Quyết định (Toma, 2026-11-11):
  - Metadata luôn bật.
  - Giá trị ghi qua audit riêng sau cờ `CRM_QUERY_AUDIT_LOG` (mặc định tắt). Đây là ngoại lệ có kiểm soát của quy tắc metadata-only.
  - Chỉ dùng log và `chat_traces`, không thêm bảng.
- Thay đổi:
  - span `tool.crm_query` thêm `attempt`, `outcome` (`ok`/`empty`/`invalid_args`/`rejected`/`crm_invalid`/`crm_error`), `ignored`, `date_from`/`date_to`, `filter_value_counts`;
  - root span thêm `crm_query_attempts`, `crm_query_outcomes`;
  - `crm_schema` thêm `cache_hits`;
  - `reporting/raw/audit.py` (`QueryAuditRecord`, `QueryAudit`), ghi vào logger `app.crm_query.audit`, không ghi `rows`;
  - hook mới `ToolSpec.on_invalid_args`, được registry gọi khi argument không validate được;
  - eval in các lần thử, thêm expect `queries_any`, `final_query_outcome_any`, `query_attempts_max` vào r1, r3, r5, q1, q2, q4, q6, q7.
- File:
  - `reporting/raw/audit.py`
  - `tools/{crm_query,crm_schema,base,registry}.py`, `core/config.py`, `agent/setup.py`
  - `evals/run_crm_agent_eval.py`, `evals/crm_agent_cases.json`
  - 3 test mới trong `test_crm_query_tool.py`
  - Docs: crm-agent README, chat-platform README, `deploy-rules.md`, `.claude/rules/flow-chat-platform.md`
- Kiểm chứng: từ `backend/`, `.\venv\Scripts\python.exe -m pytest tests` → 951 passed, 14 skipped. Eval thật chưa chạy lại.
- Ảnh hưởng contract/API/schema:
  - thêm cờ cấu hình;
  - thêm field tuỳ chọn `ToolSpec.on_invalid_args`;
  - không đổi API HTTP hay mã lỗi.

## 2026-11-11 · Tách tài liệu luồng crm-agent (D-002) · loại: thay đổi

- Vấn đề: thiết kế nằm trong `architecture.md` (276 dòng), trạng thái và lịch sử rải trong
  `current-state.md` (P5b, 12a, 12b, 12d, Validation record). `docs/ai/` chưa có dòng nào về
  `crm_schema`/`crm_query`, và mục 12d còn ghi quyết định phương án A đã bị thay.
- Quyết định/luật: tách thành README, STATE, LOG; phần cũ chép nguyên văn vào archive (duyệt:
  Toma, D-002). Tool `crm_schema`/`crm_query` mô tả theo code.
- File: `docs/ai/flows/crm-agent/*`; `architecture.md`, `current-state.md` rút gọn;
  `api_guidelines.md` sửa dòng "chưa có tool CRM".
- Kiểm chứng: từ `backend/`, `.\venv\Scripts\python.exe -m pytest tests` → 938 passed,
  14 skipped.
- Ảnh hưởng contract/API/schema: không. Không đổi code.

## 2026-11-10 · Tool `crm_schema` và `crm_query` (phương án C) · loại: thay đổi

- Vấn đề: catalog cố định (A) không trả lời được câu hỏi ngoài 4 dataset; mỗi loại câu hỏi
  mới phải sửa code.
- Thay đổi:
  - `crm_schema`: cột, quan hệ, giá trị hợp lệ của tối đa 4 bảng. Schema sống lấy từ
    `GET /api/v1/reports/tables/{t}`, cache `CRM_SCHEMA_CACHE_S`; kiểu cột và giá trị
    CHECK/ENUM từ index tĩnh `reporting/raw/schema_index.py`.
  - `crm_query`: `RawQuery` gồm `mode` list/aggregate, filter 7 toán tử, preset ngày đổi ra
    ngày cụ thể theo giờ Việt Nam. `compile_raw` kiểm hình dạng và chặn bảng/cột trong
    `policy.py`; 400 của CRM thành `crm_query_invalid` để LLM sửa.
  - `CRM_TOOLS` (mặc định `query`), `CRM_SCHEMA_CACHE_S`; `AGENT_MAX_STEPS` 5 → 6 vì câu hỏi
    CRM thường cần `crm_schema` → `crm_query` → sửa query → trả lời.
- File: `tools/crm_schema.py`, `tools/crm_query.py`, `reporting/raw/*`,
  `schemas/system/raw_query.py`, `agent/setup.py`, `core/config.py`,
  `scripts/build_crm_schema_index.py`, `evals/check_crm_query_tool.py`; test
  `tests/chatbot/test_crm_query_tool.py` (24 test). Đầu vào:
  `docs/ai/tool_instruction/ai-reporting-query.md`, `database-structure.sql`,
  `prompt_tool_report`.
- Kiểm chứng: từ `backend/`, `.\venv\Scripts\python.exe -m pytest tests` (2026-11-11) →
  938 passed, 14 skipped. Kết quả `check_crm_query_tool.py` với CRM thật: chưa được ghi lại.
- Ảnh hưởng contract/API/schema: thêm schema tool `RawQuery`, `SchemaRequest` và mã lỗi
  `crm_query_invalid` (gửi LLM, không lộ ra client). Route và SSE không đổi.
- Mở tiếp: commit code; chạy và ghi kết quả eval tay.

## 2026-11-10 · Phương án C thay phương án A cho số liệu CRM (D-005) · loại: quyết định

- Vấn đề: cùng ngày đã chốt A (LLM chỉ chọn tên trong catalog, không có tool khám phá bảng
  hay query thô). Vụ "Hohmeier" cho thấy catalog thiếu bộ lọc là agent trả lời sai mà không
  báo lỗi, và câu hỏi thực tế quá đa dạng cho catalog cố định.
- Quyết định/luật: LLM tự dựng query trên mọi bảng Reporting API qua `crm_schema` +
  `crm_query`; mặc định `CRM_TOOLS=query`. A giữ lại, bật bằng `CRM_TOOLS=catalog` hoặc
  `both`. Mở mọi dữ liệu nghiệp vụ, kể cả liên hệ khách hàng và chat; chặn khóa và bí mật
  (`app_settings`, `keygen_history`, khóa mở máy, dữ liệu sinh khóa, khóa lưu trữ, checksum
  firmware, bảng phiên/token). CRM vẫn kiểm quyền theo token. (duyệt: Toma)
- Ảnh hưởng: dữ liệu CRM đi tới nhà cung cấp LLM và có thể nằm trong `chat_history`. Ghi ở
  [decisions.md](../../decisions.md) D-005 và
  [deploy-rules.md](../../rules/deploy-rules.md).
- Đính chính: mục 12d trong archive ("option A, no raw … `run_query` tools") đã bị thay bởi
  quyết định này.
