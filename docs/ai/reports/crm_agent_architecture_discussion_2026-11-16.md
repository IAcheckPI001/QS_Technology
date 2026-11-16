# crm-agent: đặt vấn đề kiến trúc và ý tưởng phát triển (2026-11-16)

Tài liệu thảo luận, **chưa phải quyết định**. Mỗi đề xuất cần Toma duyệt trước khi triển khai.
Hiện trạng lấy từ code commit `671fe22` ([truy vết](crm_agent_execution_trace_2026-11-16.md)).
Trạng thái chính thức vẫn ở [STATE.md](../flows/crm-agent/STATE.md).

## 1. Nguồn tham khảo

Nguồn đọc ngày 2026-11-16. Ở các bảng bên dưới, "nguồn nói" là nội dung trang; phần áp dụng vào
dự án là suy luận của báo cáo.

| Nguồn | Loại | Lấy gì |
|---|---|---|
| GoClaw: [repo](https://github.com/nextlevelbuilder/goclaw), `docs/00,01,02,03,07,09,10,23` (nhánh `main`) | Agent gateway đa tenant, Go + PostgreSQL | Registry có metadata tool, chính sách tool nhiều tầng, cost theo span, failover provider, nén context |
| OpenClaw: [docs](https://docs.openclaw.ai/), các trang concepts/agent-loop, queue, memory, multi-agent; tools, skills; gateway/security | Gateway self-host, MIT | Lọc tool trước khi gọi model, tuần tự hoá lượt theo phiên, idempotency, ghi nhớ trước khi nén, `ask_user` |
| Anthropic: [Building effective agents](https://www.anthropic.com/engineering/building-effective-agents), [Context engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents), [Writing tools for agents](https://www.anthropic.com/engineering/writing-tools-for-agents) | Hướng dẫn thiết kế | Routing, gộp tool theo tác vụ, trả định danh có nghĩa, lỗi có hướng sửa, nạp context đúng lúc, ghi chú có cấu trúc |
| OpenAI Agents SDK: [guardrails](https://openai.github.io/openai-agents-python/guardrails/), [handoffs](https://openai.github.io/openai-agents-python/handoffs/), [tracing](https://openai.github.io/openai-agents-python/tracing/) | SDK | Guardrail cho từng tool (chặn hoặc sửa call), bật/tắt handoff động |
| LangGraph: [interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts) | Framework đồ thị | Tạm dừng để người duyệt, checkpoint, resume có kiểu |
| Snowflake: [semantic views](https://docs.snowflake.com/en/user-guide/views-semantic/semantic-view-yaml-spec) (Cortex Analyst) | Text-to-SQL có semantic layer | Metric và filter định nghĩa một lần, synonyms, `sample_values`/`is_enum`, `verified_queries` |

Lưu ý: README GoClaw ghi license **CC BY-NC 4.0** (phi thương mại), nên chỉ tham khảo ý tưởng,
không chép code. Docs GoClaw đọc ở nhánh `main`, trong khi nhánh mặc định của repo là `dev`.

## 2. Bức tranh hiện tại, so với các hệ thống tham khảo

| Khía cạnh | crm-agent (code hiện tại) | GoClaw / OpenClaw | Khoảng cách |
|---|---|---|---|
| Vòng lặp | Một vòng ReAct, tối đa 6 bước, 8 tool call, deadline 60s, bước cuối `tool_choice="none"` | Tương tự; OpenClaw cũng có "lượt chốt không tool". GoClaw tối đa 20 vòng | Tương đương. Thiếu: báo agent còn bao nhiêu lượt, và câu chốt khi chạm trần |
| Tool contract | `ToolSpec` có `read_only`, `concurrency_safe`, `deduplicate`, trần riêng; registry quy mọi lỗi về mã | GoClaw: capability (`read-only`/`mutating`/`async`), rate limit, che credential trong output | Gần tương đương. Thiếu: rate limit, kiểm nguồn gốc giá trị |
| Phân quyền tool | Có điểm lọc `registry.allowed()`, nhưng `scopes` luôn rỗng | Lọc theo profile, allow/deny và vai trò **trước khi gọi model**: tool bị loại không có trong schema | Chưa có |
| Phiên và đồng thời | Lease một lượt mỗi phiên (409), semaphore mỗi tiến trình | OpenClaw: hàng đợi theo phiên (steer/followup/interrupt), fence ghi transcript | Đủ cho read-only. `Idempotency-Key` mới chỉ được lưu, chưa chống xử lý trùng |
| Memory | N tin cuối của `chat_history` cộng `active_model`; kết quả tool không được lưu lại | Ghi memory trước khi nén; `MEMORY.md`; tìm trong transcript | Lượt sau không còn định danh đã tra (một nguồn của lỗi đoán username) |
| Context | Khoảng 4k token cố định mỗi bước; `<now>` chính xác tới phút đặt ngay sau phần prompt chung | Skills/guide nạp khi cần (GoClaw: inline ≤3.500 token hoặc tìm kiếm) | Guide luôn nạp đủ; tiền tố prompt đổi mỗi phút |
| Định nghĩa nghiệp vụ | Rải ở `hints.py` (`DEFAULT_FILTERS`, `DROP_WITH_DATE_RANGE`, `TABLE_NOTES`), guide và test | Snowflake: semantic model YAML (metric, filter, synonyms, verified queries) | Chưa có lớp ngữ nghĩa (backlog P1) |
| Streaming | Một `delta` duy nhất | Sự kiện `tool.call`, `tool.result`, `thinking`, chunk | Người dùng chờ khoảng 6s, không thấy tiến trình |
| Quan sát và chi phí | Span đủ; history ghi chi phí ước tính theo gpt-4o-mini; agent không ghi `cached_tokens`; còn `print()` in PII | GoClaw: cost theo span theo `provider/model`, rollup theo giờ, chặn ngân sách | Sai model và chi phí; không đo được cache |
| Prompt injection | Luật regex ở đầu vào; prompt dặn "output tool là dữ liệu" | GoClaw bọc nội dung ngoài bằng thẻ untrusted; OpenClaw đánh dấu output tool lấy từ mạng là không tin cậy | Dữ liệu CRM (ghi chú, chat khách, mở theo D-005) đi thẳng vào context |
| Duyệt hành động | Không có (chưa có tool ghi) | `ask_user`, exec approval, LangGraph `interrupt` | Bắt buộc phải có trước tool ghi |

## 3. Đặt vấn đề

Mỗi vấn đề ghi bằng chứng trong code hoặc LOG.

**V1. Giá trị trong query không có nguồn gốc.** `compile_raw` kiểm kiểu giá trị nhưng không kiểm
giá trị đó lấy từ đâu. LLM tự suy username (thiếu `@qstcnc.com`), query ra 0 dòng rồi gọi lại tới
hết lượt (LOG 2026-11-12). Guide chỉ "dặn", và model nhỏ không theo đều.

**V2. Lượt trước không còn định danh đã tra.** Kết quả tool không được lưu; lượt sau chỉ có câu
trả lời dạng văn bản trong history. Câu hỏi nối tiếp ("còn 2 sale kìa…") khiến LLM suy định danh
từ chính câu trả lời trước.

**V3. Ngân sách lượt bị đốt vào thử lại, và câu chốt không dùng được.** Tác vụ cần N query (bản
ghi đầu của từng người) vượt trần 4 lần gửi CRM. Khi chạm trần, câu trả lời là "thử lại sau" thay
vì phần đã có. Ngoài số lượt, LLM không được báo đã dùng bao nhiêu.

**V4. Luật nghiệp vụ không có chỗ ở chung.** "Khách hàng", "nhân viên sales", "kỳ", `is_current`
nằm rải ở `hints.py`, `compile.py`, guide và test. Mỗi định nghĩa mới phải sửa nhiều nơi, và không
có danh sách câu hỏi mẫu đã được xác minh (bộ eval 46 case thì chạy tay).

**V5. Chi phí và độ trễ.**
- Mỗi bước gửi khoảng 4k token cố định; gpt-4.1-mini đắt khoảng 2,5 lần gpt-4o-mini.
- `<now>` chính xác tới phút đứng ngay sau phần prompt chung, nên phần tiền tố giống nhau giữa
  các request ngắn, khả năng cao dưới mức prompt caching của OpenAI áp dụng (suy luận, cần đo).
- Agent không ghi `cached_tokens` (`providers/openai.py:190`), nên chưa đo được cache.

**V6. Phân quyền chỉ nằm ở phía CRM.** Mọi nhân viên thấy mọi tool và mọi guide. Sale thường gặp
`crm_forbidden` sau khi đã tốn bước LLM. Dịch vụ AI không biết vai trò của người hỏi.

**V7. Quan sát chưa đúng và rò dữ liệu.**
- `print()` in PII ra stdout.
- `chat_history.model` và chi phí sai khi đặt `AGENT_MODEL`.
- Không có trần chi phí.

**V8. Rủi ro injection gián tiếp.** D-005 mở dữ liệu chat và ghi chú của khách. Nội dung đó vào
context như output tool, không có đánh dấu "không tin cậy". Hiện chỉ đọc nên tác động là làm lệch
câu trả lời; trở thành rủi ro thật khi có tool ghi.

**V9. Trải nghiệm.** Không có sự kiện tiến trình; p50 khoảng 6,2s mới có chữ đầu tiên (đo
2026-11-12, gpt-4o-mini).

**V10. Mở rộng.**
- `plan()` để trống, chưa có routing.
- Thêm tool thì prompt và tool schema lớn lên tuyến tính.
- Chưa có cơ chế duyệt và idempotency cho tool ghi.

## 4. Đề xuất

Mức ưu tiên: **P0** làm ngay (nhỏ, giảm rủi ro), **P1** tăng độ đúng, **P2** chi phí và trải nghiệm,
**P3** điều kiện trước khi mở rộng.

| # | Đề xuất | Giải quyết | Ý tưởng từ | Độ lớn | Ưu tiên |
|---|---|---|---|---|---|
| E1 | Gỡ `print()`; ghi model và chi phí theo provider của vòng lặp, dùng usage thật (`turn.usage`) thay cho ước tính tiktoken; thêm `cached_input_tokens` cho bước agent | V7, V5 | GoClaw cost theo span `provider/model` | Nhỏ | P0 |
| E2 | **Kiểm nguồn gốc giá trị** (provenance guard) trong `crm_query`: filter `eq`/`in` trên cột định danh (`*.username`, `*_id`) chỉ nhận giá trị đã xuất hiện trong output tool của lượt, trong `known_values`, trong câu người dùng hoặc trong định danh lưu từ lượt trước (E3). Không khớp thì từ chối, kèm hướng sửa ("tra `user_profiles` theo tên trước") và **không tốn lượt CRM** | V1, V3 | Agents SDK tool input guardrail; Snowflake `is_enum`; Anthropic "lỗi có hướng sửa" | Vừa | P1 |
| E3 | **Ghi nhớ định danh qua lượt**: sau mỗi lượt, lưu bảng nhỏ `{tên ↔ username/id, khách ↔ id}` đã xác nhận vào `conversation_state` (có trần kích thước, chỉ giá trị lấy từ kết quả tool). Lượt sau đưa vào context ở dạng gọn | V2, V1 | Anthropic note-taking; OpenClaw ghi memory trước khi nén | Vừa | P1 |
| E4 | **Fan-out trong code**: `crm_query` thêm chế độ "mỗi giá trị một query" (vd `per_value` trên một cột, tối đa k giá trị). Code tự chạy song song k query `limit 1`, và cả nhóm tính là một call của LLM | V3 | Anthropic gộp tool theo tác vụ | Vừa | P1 |
| E5 | **Câu chốt có cấu trúc**: tool message báo `budget_left`; ở bước `tool_choice="none"` thêm chỉ dẫn hệ thống "liệt kê phần đã có và phần còn thiếu" thay vì xin thử lại | V3 | OpenClaw lượt chốt không tool | Nhỏ | P1 |
| E6 | **Semantic layer YAML** trong repo: entity, metric (`số khách = count_distinct customers.id` trừ spam), filter có tên (`nhan_vien_dang_lam`), time dimension, synonyms tiếng Việt, `verified_queries`. `compile_raw` đọc YAML thay cho hằng số trong `hints.py`; `verified_queries` vừa là few-shot vừa là regression test chạy offline | V4, V1 | Snowflake semantic views | Lớn | P1–P2 (backlog P1 đã có) |
| E7 | **Ổn định tiền tố prompt cho cache**: phần tĩnh (luật chung, guide) đặt trước; `<now>` làm tròn theo ngày hoặc chuyển sang message riêng sau phần tĩnh. Đo `cached_tokens` trước và sau, đồng thời chạy lại eval vì từng có lỗi năm khi `<now>` đặt cuối (LOG 2026-11-12) | V5 | Context engineering (suy luận về cơ chế cache của OpenAI) | Nhỏ | P2 |
| E8 | **Nạp guide khi cần**: rút phần định tuyến bảng ra khỏi guide `crm_query`, chuyển sang output `crm_schema` (đã là bước bắt buộc); hoặc routing nhẹ bằng luật để câu hỏi tài liệu không mang guide CRM | V5, V10 | Anthropic just-in-time, routing; GoClaw skill search | Vừa | P2 |
| E9 | **Tool policy theo vai trò**: CRM gửi `roles` hoặc `scopes` của nhân viên (đổi contract `CRMChatIn`); `acting_for` nạp `scopes`; `ToolSpec.required_scope` và danh sách bảng theo vai trò lọc **trước khi gọi model** (tool hoặc bảng không được phép thì không có trong schema và guide) | V6 | OpenClaw policy trước model call; GoClaw profile/allow-deny | Vừa (cần phía CRM) | P2 |
| E10 | **SSE tiến trình**: sự kiện `progress` (`tool_started`/`tool_finished`, chỉ tên tool và trạng thái, không dữ liệu) và stream token cho bước cuối | V9 | GoClaw/OpenClaw event stream; LangGraph `stream_events` | Vừa (đổi contract SSE) | P2 |
| E11 | **Đánh dấu dữ liệu không tin cậy**: cột văn bản tự do của CRM (ghi chú, nội dung chat) bọc thẻ `<untrusted>` trong `to_llm`, cộng luật prompt tương ứng | V8 | GoClaw `EXTERNAL_UNTRUSTED_CONTENT`; OpenClaw turn taint | Nhỏ | P3 (bắt buộc trước tool ghi) |
| E12 | **Khung tool ghi**: tool `mutating` luôn đi qua bước xác nhận (agent trả "đề xuất hành động", CRM hiển thị nút duyệt, lượt sau mới thực thi); `Idempotency-Key` chống trùng thật; timeout ở tool ghi tính là "chưa rõ" và phải kiểm trạng thái trước khi gọi lại | V10, V8 | LangGraph `interrupt`; OpenClaw `ask_user`, idempotency, "timeout = unknown" | Lớn | P3 |
| E13 | **Sub-agent "chuyên viên số liệu"** khi số tool hoặc bảng lớn: vòng lặp con có context riêng, chạy schema → query, trả về bản tóm tắt gọn; vòng chính chỉ thấy một tool `crm_analyst` | V10, V5 | Anthropic orchestrator-workers, sub-agent; GoClaw delegate | Lớn | Theo dõi, chưa làm |

**Không nên lấy** (ngoài phạm vi kênh CRM nội bộ):
- Gateway đa kênh, memory dạng file và "dreaming".
- Sandbox exec, skills hot-reload.
- Failover đa provider. Có thể cân nhắc sau khi có nhu cầu SLA.

## 5. Lộ trình gợi ý

1. **Đợt 0, vệ sinh:** E1, cộng luật username trong guide (đã có trong STATE). Không đổi contract.
2. **Đợt 1, độ đúng:** E2, E3, E4, E5. Đo bằng eval 27 case và thêm case nhiều sale.
   - Kỳ vọng: giảm trượt do đoán định danh và do chạm trần.
   - Rủi ro: E2 chặt quá có thể chặn query hợp lệ. Nên có cờ chuyển giữa `warn` và `reject` để đo trước.
3. **Đợt 2, chi phí và trải nghiệm:** E7 (đo trước), E8, E6 (làm dần, bắt đầu từ các định nghĩa đã
   chốt), E10 (cần cập nhật `api_guidelines.md`).
4. **Đợt 3, trước khi có tool ghi:** E9 (cần phía CRM), E11, E12.

## 6. Câu hỏi cần quyết

1. Thứ tự ưu tiên ở trên có hợp lý không, hay làm E6 (semantic layer) trước E2–E4?
2. E2: khi giá trị không có nguồn gốc thì **từ chối** (chặt, tốn một lượt thử) hay **cảnh báo**
   (ghi trace, vẫn gửi CRM)?
3. E3: lưu định danh nhân viên/khách vào `conversation_state` (nằm trong `chat_history`) có chấp
   nhận được về dữ liệu không? D-005 đã cho phép dữ liệu CRM nằm trong history.
4. E9 và E10 đổi contract với CRM backend. Ai là đầu mối phía CRM?
5. Có kế hoạch tool ghi (tạo phiếu, cập nhật khách) trong quý này không? Nếu có, E11 và E12 cần
   lên sớm.
