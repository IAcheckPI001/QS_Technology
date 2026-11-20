# Nhật ký luồng crm-agent

Nhật ký phát triển, **mục mới nhất ở trên**. Chỉ thêm mục mới, không sửa mục cũ; nếu mục
cũ sai, thêm mục mới đính chính. Sau khi thêm mục, viết lại [STATE.md](STATE.md).
Mẫu mục: [../_template/LOG.md](../_template/LOG.md).

Các mục tới 2026-11-10 (nguyên văn từ `current-state.md` và `architecture.md`):
[LOG-archive-2026-11-11.md](LOG-archive-2026-11-11.md).

## 2026-11-20 · Kiểm D-014 trên 2 câu so sánh kèm tư vấn: hết đọc nhầm cột, còn lỗi tổng hợp · loại: kiểm chứng

- Dữ liệu: phiên `fd5e7814…`, 06:15 UTC, gpt-4.1-mini, backend `0f69b58` (mặc định 2 + 4, cắt cột).
- Cắt cột chạy đúng: mọi bảng chọn model chỉ còn cột của hai model được hỏi.
- "So sánh F54 và F86, nên lấy con nào, F54 có yếu không": 1 lần gọi, 11.133 token vào (không cache),
  694 ra, 0,004292 USD, 15,4 s. Đúng: 4/6 trục, kích thước, màn hình, I/O, Look-Ahead 250/500 và thời gian
  xử lý block 250/500 (đã ở "Khác nhau"), tuổi dao, EtherCAT. Lỗi: câu spindle ghi "F86 … đồng thời 2 spindle,
  F86 … 4" (2 là của F54); vẫn bỏ sót trục PLC 0 so với 6/8. Tư vấn chọn model dựa vào số trục, có điều kiện.
- "F86 khác gì F10T, cảm ứng có bền không, bằng giá nên chọn cái nào": 3 lần gọi trong một bước (2 lần so sánh
  gần trùng + 1 `handoff` về giá), 22.860 token vào (cache 15.488), 0,00486 USD, 9,7 s. Hết lỗi đọc nhầm cột
  (bảng General của F86/F10T giống nhau, không còn gán sai); độ bền cảm ứng nói rõ tài liệu không có; giá chuyển
  bộ phận kinh doanh. Lỗi: dòng "Cả hai đều…" nằm trong "Khác nhau"; còn "kích thước nhỏ gọn hơn thì chọn F86".
- Chưa chạy: C3 (ASTRO-10S), C4 (3 model), C5 (F86E), C7 (website).
- Kết luận: cắt cột bảng đạt mục tiêu; hạn mức 2 + 4 vẫn tạm (câu F54–F86 lấy bảng Compensation giống nhau,
  thiếu Multi axis). Lỗi còn lại là bước tổng hợp của LLM. Đề xuất: code tính sẵn dòng khác/giống từ bảng đã cắt
  cột và đưa vào output tool; gộp lần so sánh trùng model trong cùng lượt.

## 2026-11-20 · So sánh: cắt cột bảng theo model được hỏi, mặc định 2 + 4 (quyết định tạm D-014) · loại: thay đổi, quyết định

- Vấn đề: kiểm thật 2 + 4 (mục bên dưới): bảng chọn model 4 cột làm LLM ghi giá trị cột F54 cho F86;
  "Thời gian xử lý block 500/500" xếp vào "Khác nhau"; vẫn bỏ sót dòng của bảng General.
- Quyết định (Toma, 2026-11-20): làm cả hai (cắt cột + mặc định 2 + 4), **đánh dấu tạm** để kiểm trên các
  câu sau ([D-014](../../decisions.md); bộ câu C1–C7: [kế hoạch](../../reports/crm_agent_dot1_plan_2026-11-20.md) mục 9).
- Thay đổi (commit `15c9c6e`, nhánh `claude/dot1-e-d`):
  - `retrieval/table_columns.py` (mới) `trim_model_columns`: cột có tiêu đề chỉ ra đúng một model của
    registry (mã/alias, vd ASTRO-10S → 10S) mà không thuộc model được hỏi thì bị bỏ; cột khác giữ; bảng lệch
    số cột hoặc không có cột của model được hỏi giữ nguyên. `Retriever` chỉ áp khi so sánh.
  - Mặc định `RETRIEVAL_COMPARE_PER_MODEL=2`, `RETRIEVAL_COMPARE_SHARED=4` (`config.py`, `RetrieverConfig`).
  - Guide `product_docs_ask`: so từng cặp trước khi xếp "Khác/Giống"; đọc theo tiêu đề cột, đọc hết dòng
    bảng; không kết luận "lớn/nhỏ/gọn hơn" từ nhiều số đo.
- File test: `test_retrieval.py` (+4). Kiểm chứng: `pytest tests` → 1117 passed, 14 skipped, 1 failed có sẵn
  (CSV CRLF). Mức chín: code + test fake.
- Ảnh hưởng: mặc định retriever so sánh đổi cho cả website (website-qa LOG); D-014 mới.
- Chưa kiểm / mở tiếp: chạy C1–C7; Toma có thể bỏ hai biến trong `.env` để dùng mặc định mới.

## 2026-11-20 · Thử so sánh 2 chunk riêng + 4 chunk chung: nguồn đa dạng hơn, lộ lỗi đọc nhầm cột bảng · loại: kiểm chứng

- Dữ liệu: phiên `fd5e7814…`, 05:59 UTC, gpt-4.1-mini, `.env` của Toma đặt `RETRIEVAL_COMPARE_PER_MODEL=2`,
  `RETRIEVAL_COMPARE_SHARED=4` (code mặc định vẫn 3 + 2).
- Nguồn: bỏ được hai trang tóm tắt lặp lại; mỗi câu có tổng quan + thông số của từng model và 4 mục bảng
  chọn model (F86–F54: Hardware, General, Tool Manager, Operation; F86–F10T: Hardware, General, Tool
  Manager, Multi axis). Token: 10.876 và 11.175 vào; 0,003566 và 0,003395 USD; 1 lần gọi tool mỗi câu.
- "F86 khác F54": thêm đúng quản lý tuổi dao; đã tách "Khác nhau"/"Giống nhau". Vẫn bỏ sót số trục PLC
  (0 so với 6/8) và spindle đồng thời (2 so với 4) trong bảng General; xếp Look-Ahead 500/250 vào "Giống nhau".
- "So sánh F86 và F10T": **sai số liệu do đọc nhầm cột**: "F86 không có trục PLC", "spindle đồng thời F86 là 2"
  lấy từ cột F54; bảng General ghi F86 và F10T giống hệt nhau (6, tùy chọn 8; 4 spindle). "Thời gian xử lý
  block 500 so với 500" bị xếp vào "Khác nhau". Màn hình cảm ứng của F10T đã có.
- Nhận định: bảng chọn model có 4 cột (F54, F86, F10T, ASTRO-10S); khi so sánh 2 model, các cột thừa làm
  LLM gán nhầm cột. Đề xuất: khi so sánh, cắt bảng chỉ còn cột tên thuộc tính và cột của các model được hỏi;
  guide: dòng nào giá trị giống nhau thì không đưa vào "Khác nhau". Chờ Toma quyết.

## 2026-11-20 · Kiểm lại so sánh với gpt-4.1-mini: một lần gọi, đủ thông số chính · loại: kiểm chứng

- Dữ liệu: phiên `fd5e7814…`, 05:44–05:45 UTC, `AGENT_MODEL=gpt-4.1-mini`, backend `f8fc979`.
- "F86 khác F54": 1 lần `product_docs_ask`, 8 nguồn (đủ chunk tổng quan hai model); 11.996 token vào
  (cache 6.272), 560 ra, 0,003356 USD, 11,2 s. Đúng nguồn: 6/4 trục, EtherCAT, kích thước, màn hình,
  I/O, spindle 2/1, Look-Ahead 500/250, điểm giống nhau. Thiếu quản lý tuổi dao, đa trục tùy chọn (bảng
  Tool Manager/Multi axis không vào 2 suất chung lần này).
- "So sánh F86 và F10T": 1 lần gọi, 11.811 token, 557 ra, 0,003294 USD, 9,0 s. Đúng nguồn (kể cả RTCP
  tùy chọn), trừ suy luận "F10T nhỏ gọn hơn F86" (F10T ngắn hơn nhưng rộng, dày hơn); thiếu "cảm ứng".
- Cả hai chưa tách mục "Khác nhau"/"Giống nhau" nhưng mỗi dòng ghi rõ "cả hai" hoặc giá trị từng model.
- Kết luận: G4 đạt trừ một suy luận kích thước tổng hợp; G5 sát ngưỡng (11,8–12,0k). Mở tiếp: guide cấm
  kết luận "lớn/nhỏ/gọn hơn" từ nhiều số đo; cân nhắc `RETRIEVAL_COMPARE_SHARED=3`.

## 2026-11-20 · Kiểm thật bản sửa so sánh (`f8fc979`): đủ số trục, nhưng chạy gpt-4o-mini · loại: kiểm chứng

- Dữ liệu: phiên `fd5e7814…`, 2 lượt 05:38–05:39 UTC; **`AGENT_MODEL` vẫn là gpt-4o-mini** (đặt khi kiểm G2),
  không phải model mục tiêu gpt-4.1-mini.
- Chọn chunk đúng thiết kế: lần so sánh trả 8 nguồn, có chunk tổng quan "6 AXIS"/"4 AXIS" của từng model.
- "F86 khác F54": đủ số trục 6/4, kích thước, màn hình, I/O, [S#] sau từng giá trị. Nhưng agent gọi
  `product_docs_ask` 4 lần trong 3 bước (2 lần bị từ chối `based_on_sources` dùng S# của lượt trước, rồi
  so sánh + tra riêng F54): 19.051 token vào, 0,002931 USD, 24,5 s. Thiếu spindle 2/1, quản lý tuổi dao,
  đa trục tùy chọn (có trong chunk); không tách "Khác nhau"/"Giống nhau".
- "So sánh F86 và F10T": 1 lần gọi, 11.774 token, 0,001589 USD, 8,2 s; đúng nguồn, hết "µs", [S#] theo giá
  trị. Sai một suy luận: "F86 có kích thước tổng thể lớn hơn" (326×185×30 so với 254×195×40: F86 dài hơn,
  hẹp hơn, mỏng hơn). Thiếu "cảm ứng" của F10T; không tách "Khác nhau"/"Giống nhau".
- Mở tiếp: kiểm lại với `AGENT_MODEL=gpt-4.1-mini`; guide cấm suy luận so sánh tổng hợp (lớn/nhỏ hơn) từ
  nhiều số đo; cân nhắc chặn bằng code lần tra riêng một model đã có trong lần so sánh cùng lượt.

## 2026-11-20 · Câu so sánh: chunk riêng của từng model không còn bị bảng chung đẩy ra · loại: thay đổi

- Vấn đề: kiểm thật (mục cùng ngày bên dưới) thiếu số trục/kích thước F86–F54: chunk chung (bảng chọn
  model, khớp cả hai model, điểm cao) chiếm hết hạn mức của mỗi model; [S#] chỉ gom ở cuối; tự thêm "µs".
- Thay đổi (commit `a627bd8`, nhánh `claude/dot1-e-d`): `Retriever._select_comparison`:
  chunk khớp ≥ 2 model là chunk chung; mỗi model giữ `RETRIEVAL_COMPARE_PER_MODEL` (3) chunk riêng, xen kẽ;
  chunk chung giữ `RETRIEVAL_COMPARE_SHARED` (2) + suất riêng chưa dùng. Guide `product_docs_ask`: [S#] ngay
  sau từng giá trị, tách "Khác nhau"/"Giống nhau", mở đầu bằng số trục/giao tiếp/kích thước, không thêm
  đơn vị nguồn không ghi.
- Kiểm chứng: `pytest tests` → 1113 passed, 14 skipped, 1 failed có sẵn (CSV CRLF). Mức chín: code + test fake.
- Ảnh hưởng: biến mới `RETRIEVAL_COMPARE_SHARED` (deploy-rules); website so sánh dùng chung cách chọn.
- Chưa kiểm / mở tiếp: Toma hỏi lại "F86 khác F54 thế nào?", "So sánh F86 và F10T"; `run_retrieval_eval.py`.

## 2026-11-20 · Kiểm thật gói E+D: so sánh một lần gọi, token giảm 63%, còn thiếu số trục · loại: kiểm chứng

- Dữ liệu: phiên `fd5e7814…`, backend local chạy `5685901`, đọc qua `/history`, `/trace`, `/retrieval`.
- "F86 khác F54 thế nào?" (gpt-4.1-mini): 1 lần `product_docs_ask` (trước 3), 8.324 token vào (trước
  22.804), 0,00267 USD. Đối chiếu toàn văn 6 chunk: mọi ý đúng nguồn (EtherCAT, spindle 2/1, Look-Ahead
  500/250, I/O, tuổi dao, màn hình). **Thiếu số trục 6/4 và kích thước**: 6 chunk là bảng chọn model và
  trang thông số, không có chunk tổng quan "BỘ ĐIỀU KHIỂN n AXIS" của từng model.
- "So sánh F86 và F10T": 1 lần gọi, 10.530 token; nội dung đúng nguồn, trừ đơn vị "µs" của Block
  Processing Time (bảng không ghi đơn vị) và mục "Khác biệt" lẫn thuộc tính giống nhau.
- Cả hai câu chỉ ghi [S1]…[S6] ở cuối, chưa trích theo từng thuộc tính như guide yêu cầu.
- "F54 có bao nhiêu trục" (gpt-4o-mini, câu lặp lại): gọi tool ngay bước 1, đúng "4 trục" [S2][S3];
  đường ép gọi tool (`forced_tool_call`) chưa phát sinh nên chưa kiểm thật được.
- Một lượt lỗi 401 `invalid_api_key` lúc khởi động lại backend (cấu hình khóa), lượt gửi lại thành công.
- Kết luận theo kế hoạch: G4 đạt một phần (1 lần gọi, không kết luận sai; thiếu số trục), G5 đạt, G2 đạt
  trên mẫu này. Mở tiếp: thử `RETRIEVAL_COMPARE_PER_MODEL=4` hoặc ưu tiên chunk tổng quan khi so sánh;
  guide: trích nguồn theo thuộc tính, không thêm đơn vị không có trong nguồn.

## 2026-11-20 · Đợt 1 gói E+D: câu so sánh gọi một lần, bắt buộc tra nguồn · loại: thay đổi

- Vấn đề: P5 (câu "F86 khác F54" gọi tool 3 lần, 22,8k token, kết luận sai bù rơ/PLC/ATC) và lượt
  "F54 có bao nhiêu trục" (gpt-4o-mini) trả lời từ lịch sử, không có nguồn ([kế hoạch](../../reports/crm_agent_dot1_plan_2026-11-20.md)).
- Thay đổi (commit `ccc5f5a`, nhánh `claude/dot1-e-d`):
  - Gói E: retriever giữ `RETRIEVAL_COMPARE_PER_MODEL=3` chunk/nhóm mỗi model khi so sánh; mô tả
    `product_docs_ask` yêu cầu so sánh gọi MỘT lần; guide thêm khung so sánh theo thuộc tính, chỉ nói
    "khác" khi cả hai giá trị có nguồn, đọc ✓/✗/(Option) của bảng chọn model.
  - Gói D: `ToolSpec.requires_call`; `AgentRunner` bỏ câu trả lời không gọi tool nào khi có trích nguồn
    không hợp lệ hoặc tool khai báo `requires_call` khớp tin nhắn (`product_docs_ask`: nhắc model trong
    registry), chạy lại một bước `tool_choice="required"` (ép một lần, như `reset_tool_choice`). Root
    span `forced_tool_call`. `ToolChoice` thêm `required`.
- File: `retrieval/retriever.py`, `core/config.py`, `tools/{base,product_docs}.py`,
  `agent/{runner,prompts}.py`, `schemas/system/agent.py`; test `test_retrieval.py` (+2),
  `test_agent_guards.py` (+3, sửa 1).
- Kiểm chứng: từ `backend/`, `pytest tests` → 1112 passed, 14 skipped, 1 failed có sẵn (CSV CRLF trong
  worktree). Mức chín: code + test bằng fake.
- Ảnh hưởng: biến mới `RETRIEVAL_COMPARE_PER_MODEL` (deploy-rules); hành vi website so sánh đổi (website-qa
  LOG cùng ngày). Không đổi HTTP/SSE.
- Chưa kiểm / mở tiếp: chưa merge; Toma kiểm thật G2/G4/G5 (5 câu so sánh, câu lặp lại với gpt-4o-mini) và
  `run_retrieval_eval.py`; bước tiếp theo C1–C3.

## 2026-11-20 · Duyệt kế hoạch Đợt 1 (Q1–Q5) · loại: quyết định

- Quyết định (duyệt: Toma, 2026-11-20; căn cứ: [kế hoạch](../../reports/crm_agent_dot1_plan_2026-11-20.md) mục 7):
  - Q1 thứ tự: E + D → C1–C3 → A → B → C4 → đo ngưỡng chunk;
  - Q2 lưu username/id nhân viên, id khách trong `conversation_state.facts`, chỉ từ output tool, TTL 10 lượt;
  - Q3 kiểm nguồn gốc bắt đầu `CRM_QUERY_PROVENANCE=warn`, 1–2 tuần sau chuyển `reject`;
  - Q4 ngưỡng khởi đầu: 3 lượt agent, 10 lượt đọc DB, 15k token/lượt, 50% ngân sách, 3 chunk/model khi so sánh;
  - Q5 tóm tắt cuộn và dùng lại nguồn lượt trước dời sang Đợt 2.
- Mở tiếp: Toma chạy eval mốc trước khi merge Đợt 1.

## 2026-11-20 · Kế hoạch Đợt 1: context phiên, điều khiển vòng lặp, nguồn và so sánh · loại: đánh giá

- Vấn đề: P1–P6 ([kế hoạch](../../reports/crm_agent_dot1_plan_2026-11-20.md) mục 1): kết quả tool và
  định danh không lưu qua lượt; nạp toàn bộ history; chạm trần trả "thử lại sau"; định danh không kiểm
  nguồn gốc; câu so sánh gọi 3 lần mà sai; ngưỡng chunk cosine 0,25 chưa đo.
- Đề xuất: 5 gói (A context ba lớp, B kiểm nguồn gốc `warn`→`reject`, C tín hiệu dừng + bước chốt có
  cấu trúc + fan-out, D bắt buộc tra nguồn, E so sánh theo hạn mức từng model), tiêu chí G1–G6,
  thứ tự triển khai; tham khảo Agents SDK, Anthropic, LangGraph, OpenAI Cookbook.
- Chưa kiểm / mở tiếp: chờ Toma duyệt Q1–Q5; Toma chạy eval mốc trước khi bắt đầu.

## 2026-11-20 · Đợt 0 hoàn tất trên nền B3: model của agent, sổ usage, cached tokens, luật username (E1) · loại: thay đổi

- Vấn đề: sau B3 (D-013, chat-platform LOG 2026-11-18), nhánh chính còn thiếu bốn điểm của Đợt 0:
  history ghi `OPENAI_MODEL` cả ở lượt agent; usage cộng từ span nên mất khi vượt
  `CHAT_TRACE_MAX_SPANS`, lời gọi hết giờ/bị huỷ không được tính; bước agent không ghi cached tokens;
  guide `crm_query` chưa cấm tự suy username.
- Quyết định: Toma yêu cầu làm tiếp Đợt 0 trên nền B3 (2026-11-20). Giữ `core/pricing.py`,
  `LLM_PRICES_JSON`, `turn_usage.py` của B3; bỏ bản Đợt 0 cũ trên nhánh
  `claude/agent-crm-development-29f518` (commit `e8223e9`, `8351d71`: trùng B3, không merge).
- Thay đổi (commit `e77f08e`, nhánh `claude/dot0-on-b3` tách từ `6e1f465`):
  - `core/tracing.py`: `UsageEntry`, `Trace.usage`, `record_usage`; `usage_by_model` đọc sổ (sổ rỗng
    thì đọc span như cũ), thêm `estimated_calls`.
  - `providers/openai.py`: mọi lời gọi ghi sổ qua `_metered`; hết giờ, bị huỷ, stream ngắt → mục ước
    tính; lỗi HTTP/kết nối không ghi. `chat_complete_tools` đọc cached tokens, ghi lên span
    `llm.chat_tools` của runner.
  - `services/turn_usage.py`, `turn_sources.py`, `schemas/history.py`: `estimated_calls` trong
    `retrieval_snapshot.usage` và `usage` của `/history`.
  - `services/chat_service.py`: `_turn_model` → `AgentRunner.model` ở lượt CRM chạy agent (3 nhánh
    ghi history và `snapshot.model`).
  - `tools/crm_query.py`: luật "username, mã, UUID chỉ dùng nguyên văn từ kết quả tool…".
  - Test: `test_usage_ledger.py` (mới, 8), `test_retrieval_snapshot.py` (fake service).
- Kiểm chứng: từ `backend/`, `pytest tests` → 1107 passed, 14 skipped, 1 failed có sẵn
  (`test_f86_baseline`, CSV CRLF trong worktree). Mức chín: code + test bằng fake.
- Ảnh hưởng contract/API/schema/cấu hình: `/history` thêm `usage.estimated_calls` (chỉ thêm);
  `model` của lượt agent đổi sang `AGENT_MODEL`. Không biến môi trường mới, không SQL.
- Chưa kiểm / mở tiếp: chưa merge; chưa chạy trên server thật; chưa eval tác động của luật username.

## 2026-11-20 · Lượt thật trên kênh CRM: pipeline vs agent, chất lượng câu trả lời F86/F54 · loại: kiểm chứng

- Dữ liệu: phiên `c999efd3…`, đọc qua `/chatbot/sessions/{id}/trace|retrieval` của backend local.
- Hai lượt F86 (2026-11-19 22:41, 22:52) chạy `flow=pipeline` (backend lúc đó đặt
  `CRM_CHAT_FLOW=pipeline`): "các trục" đúng ý (6 trục) nhưng tên trục X–C lấy từ lịch sử, không
  có nguồn; "cấu hình, cách sử dụng" chỉ có Installation Manual F86, phần "cách sử dụng" không có
  trong tài liệu; 4/6 chunk chỉ là tiêu đề trang hình (doc-ingest).
- Lượt F54 (2026-11-19 23:08) sau khi bật lại agent: `flow=agent`, 2 bước LLM + 1
  `product_docs_ask`, đúng "4 trục" [S2][S3]; 9.914 token vào (analysis trong tool 5.107, không
  cache), 9,2 s, một `delta`.
- Mở tiếp: E7/E8 (giảm prompt analysis), doc-ingest gộp chunk chỉ có tiêu đề; nạp tài liệu vận hành F86.

## 2026-11-19 · `product_docs_ask` tra cứu trên doc_chunks_v2 · loại: thay đổi

- Theo website-qa (D-009 bước 6): retriever dùng chung chuyển sang `DocChunkV2Repository`, nên tool
  `product_docs_ask` cũng đọc `doc_chunks_v2`, chỉ chunk `approved` khi `RETRIEVAL_APPROVED_ONLY=true` (mặc định).
  Chi tiết: [website-qa/LOG.md](../website-qa/LOG.md) mục 2026-11-19.
- `evals/run_crm_agent_eval.py` (hàm `doc_repository()`) và `compare_agent_models.py` dựng retriever như production.

## 2026-11-16 · Sửa `backend/.env.example` cho khớp `config.py` (K4 của đợt dọn) · loại: thay đổi

- Vấn đề: `.env.example` lệch code sau đợt dọn (mục dưới): thiếu `AGENT_MODEL`, `CRM_SCHEMA_CACHE_S`,
  `CRM_QUERY_AUDIT_LOG`; `AGENT_MAX_STEPS=5` (code 6); còn `CRM_REPORT_MAX_ITEMS` đã bỏ;
  `CRM_REPORT_ENABLED=true` kèm URL ngrok.
- Thay đổi: Toma sửa tay `backend/.env.example` (+9/−3 dòng). Agent không đọc nội dung file
  (TR-07, quyền đọc `.env*` bị chặn) nên ghi nhận theo xác nhận của Toma, chưa đối chiếu từng biến.
- Kiểm chứng: không có (file mẫu, không có test).
- Ảnh hưởng contract/API/schema: không.
- Mở tiếp: đặt `AGENT_MODEL=gpt-4.1-mini` ở môi trường chạy; header `ngrok-skip-browser-warning`.

## 2026-11-16 · Dọn luồng trước Đợt 0/1: gỡ debug, xoá phương án A, gom code trùng (D-010) · loại: thay đổi, quyết định

- Vấn đề: trước Đợt 0/1 cần luồng sạch. Ba lượt rà (code agent/tools/reporting; wiring, config,
  test; tài liệu) trên `671fe22` tìm ra `print()` in dữ liệu CRM, phương án A không còn dùng nhưng C
  vẫn import từ module của A, code chết/trùng và tài liệu lỗi thời.
- Quyết định (Toma): xoá hẳn A (D-010, thay một phần D-005); chỉ dọn trên đường agent; tài liệu cũ
  chuyển vào `docs/ai/archive/`; giữ rollback `CRM_CHAT_FLOW=pipeline` (D-006).
- Thay đổi (nhánh `claude/agent-crm-development-29f518`, mỗi bước một commit):
  - K1: gỡ `print()` ở `agent/runner.py`, `providers/crm_api.py`; bỏ code comment, TODO cũ.
  - K2a: `crm_credential`, `query_all` → `tools/crm_common.py`; `api_column`, `render_value` →
    `reporting/raw/render.py`; `DATE_PRESETS` → `reporting/dates.py`.
  - K2b: xoá `tools/crm_report.py`, `crm_records.py`, `reporting/{catalog,engine,validate,report_api,records}.py`,
    `reporting/datasets/`, `schemas/system/{report,records}.py`, `CrmListClient`, setting `crm_tools`,
    `crm_report_max_items`, `CATALOG_PREFERENCE`, 5 file test và `evals/check_crm_report_contract.py`.
    Thêm `tests/chatbot/crm_fakes.py`, `test_crm_render.py`, test trace 401 cho `crm_query`.
  - K3: một nguồn `TOOL_CALL_LIMIT` (`tools/base.py`) và `crm_query_invalid`; `AgentLimits.max_steps`
    6; `build_messages` bắt buộc `specs`; bỏ nhánh không thể xảy ra của `outcome_of_error`,
    `LLMCapabilities.tool_choice_required`, re-export `Deadline`, import `RetrievalScope`;
    `main.py` dùng `effective_agent_model`.
  - Tài liệu: archive 5 file (có `archive/README.md`); `check_ai_docs.py` bỏ qua `docs/ai/archive`;
    sửa README, api_guidelines, architecture, AGENTS.md, decisions (D-010), deploy-rules,
    current-state, `crm-reporting-api-requests.md` (cột trạng thái), hai báo cáo.
- Chưa làm: K4 `backend/.env.example` (file nằm ngoài quyền đọc của agent; việc cần sửa ghi ở
  STATE và deploy-rules).
- Ngoài phạm vi, để đợt riêng (code chết dùng chung): `Branch`/`branch` luôn `None`,
  `ContextLoader.resolve_retrieval_scope` và `RetrievalScope.collections`, `schemas/outbound.py`,
  `InboundRequest.resources`, `orchestration.summarize_statuses`, import thừa ngoài đường agent,
  fake test trùng, `config.embedding_input_usd_per_million`.
- Kiểm chứng: từ `backend/`, `pytest tests` → 1015 passed, 14 skipped, 1 failed (`test_f86_baseline`,
  CSV CRLF trong worktree, có sẵn); `check_ai_docs.py` đạt. Chưa chạy eval thật (cần OpenAI, CRM):
  Toma chạy lại `run_crm_agent_eval.py`.
- Ảnh hưởng contract/API/schema: không đổi HTTP/SSE. Tool `crm_report`/`crm_records` và mã
  `http.crm_list` không còn; `CRM_TOOLS`, `CRM_REPORT_MAX_ITEMS` bị bỏ qua nếu còn trong `.env`.

## 2026-11-16 · Thảo luận kiến trúc, đối chiếu GoClaw/OpenClaw và các hệ thống khác · loại: đánh giá

- Báo cáo: [crm_agent_architecture_discussion_2026-11-16.md](../../reports/crm_agent_architecture_discussion_2026-11-16.md).
  Gồm 10 vấn đề (V1–V10) và 13 đề xuất (E1–E13). **Chưa duyệt**, chờ Toma trả lời mục 6 của báo cáo.
- Phát hiện thêm: bước agent không ghi `cached_tokens` (`providers/openai.py` `chat_complete_tools`),
  nên chưa đo được prompt caching.
- File: báo cáo mới. Không đổi code.
- Ảnh hưởng contract/API/schema: không.

## 2026-11-16 · Truy vết luồng thực thi; phát hiện log debug chứa PII · loại: đánh giá

- Báo cáo truy vết request → response, LLM/context/memory/tool, phân quyền, lỗi, handoff:
  [crm_agent_execution_trace_2026-11-16.md](../../reports/crm_agent_execution_trace_2026-11-16.md).
- Phát hiện mới:
  - `print()` debug ở `agent/runner.py:289` và `providers/crm_api.py:199,239,255` in argument
    query, body và toàn bộ rows CRM ra stdout;
  - `chat_history.model` và chi phí theo `OPENAI_MODEL`/đơn giá gpt-4o-mini, không theo
    `AGENT_MODEL`;
  - `AgentLimits.max_steps` mặc định 5 trong dataclass, `config.py` 6.
- File: báo cáo mới, STATE. Không đổi code.
- Ảnh hưởng contract/API/schema: không.
- Mở tiếp: gỡ `print()`; ghi model/chi phí theo provider của agent.

## 2026-11-16 · Đối chiếu nhật ký với code: phương án C đã commit, tồn đọng còn lại · loại: đánh giá

- Vấn đề: STATE (2026-11-12) và `current-state.md` còn ghi phương án C "staged/chưa commit",
  "eval tay chưa chạy", 951 passed; STATE chưa phản ánh mục 2026-11-14.
- Đính chính (kiểm code trên `feature/deploy_ai_service`, `671fe22`):
  - `crm_schema`, `crm_query`, `reporting/raw/*`, `schemas/system/raw_query.py` đã commit ở
    `4a4b5b5` (2026-11-14), gồm thay đổi giới hạn gọi tool mục 2026-11-12
    (`MAX_CRM_QUERIES_PER_TURN = 4`, `MAX_QUERY_ATTEMPTS_PER_TURN = 6`, runner không trừ trần chung
    với call `tool_call_limit`).
  - Eval tay đã chạy (78/81, mục 2026-11-12).
- Tồn đọng xác nhận trong code:
  - guide `crm_query` chưa có luật "username chỉ lấy nguyên văn từ kết quả tool", chưa hướng dẫn
    tách query bản ghi đầu/cuối của từng người;
  - luật "trả lời phần đã có" khi chạm giới hạn có trong `agent/prompts.py` từ 2026-11-02 nhưng
    vẫn ra câu "thử lại sau" (mục 2026-11-12);
  - `evals/crm_agent_cases.json` (46 case) chưa có case nhiều sale hai lượt;
  - `backend/.env.example` thiếu `AGENT_MODEL`, `CRM_TOOLS`, đặt `AGENT_MAX_STEPS=5` (code mặc
    định 6), `CRM_REPORT_ENABLED=true` kèm URL ngrok;
  - `AgentRunner.plan()` vẫn để trống; chưa có phân quyền tool, SSE tiến trình, stream token.
- File: `docs/ai/flows/crm-agent/STATE.md`, `docs/ai/current-state.md`. Không đổi code.
- Kiểm chứng: từ `backend/`, `.\venv\Scripts\python.exe -m pytest tests` → 1120 passed,
  14 skipped (commit `671fe22`).
- Ảnh hưởng contract/API/schema: không.
- Mở tiếp: luật username và trả lời khi chạm giới hạn trong guide; case eval nhiều sale; sửa
  `.env.example`; chốt r1.

## 2026-11-14 · Registry thêm model 10S, 10i: ảnh hưởng tìm model theo tiêu chí và báo cáo · loại: thay đổi

- Registry chung (chi tiết: website-qa LOG cùng ngày) thêm `10S`, `10i` (tên tạm, chờ CRM chuẩn hóa). Với crm-agent:
  `product_docs_ask` tìm theo tiêu chí trả thêm 10S/10i ("EtherCAT" 11 model; "EtherCAT, không Mechatrolink" 4 model →
  `ask_selection` thay `lookup_each`); "10i" không còn là alias mơ hồ; `crm_report` nhận product_name "10S"/"10i".
- Test cập nhật: `test_catalog_lookup_tool.py`, `test_crm_catalog_flow.py`, `test_report_validate.py`. Không đổi code
  agent/tool.

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
