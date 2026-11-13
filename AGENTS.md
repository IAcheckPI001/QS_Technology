# QS Technology — hướng dẫn cho AI agent

File này là nguồn chung cho mọi nền tảng AI (Claude Code, Copilot, nền tảng khác).
`CLAUDE.md` và `.github/copilot-instructions.md` chỉ trỏ về đây.

## Bối cảnh

Chatbot AI phân tích, nạp dữ liệu và truy vấn tài liệu cho QS Technology.

- Frontend: React/Vite (JavaScript/JSX) tại `src/`; BFF của widget tại `widget-backend/`.
- Backend: FastAPI/Python tại `backend/app/`; database: Supabase Cloud (Postgres + pgvector).
- Tool nạp tài liệu offline: `backend/app/modules/doc_ingest/`, venv riêng `.venv-ingest`.

## Chỉ mục luồng

Xác định task thuộc luồng nào, rồi đọc tài liệu của luồng đó trước khi mở code.
Mỗi luồng đã tách có ba file trong `docs/ai/flows/<luồng>/`: `README.md` (thiết kế),
`STATE.md` (trạng thái hiện tại), `LOG.md` (nhật ký, mới nhất ở trên).

Với mọi luồng, đọc `README.md` và `STATE.md`; đọc `LOG.md` khi cần biết vì sao một quyết
định được đưa ra. Mã nguồn tính từ `backend/` (trừ `src/`, `widget-backend/`).

| Luồng | Code | Tài liệu | Test nhanh (từ `backend/`) |
|---|---|---|---|
| **crm-agent**: agent gọi tool trên kênh CRM (`crm_schema`/`crm_query`, `crm_report`/`crm_records`, `product_docs_ask`) | `app/modules/chatbot/{agent,tools,reporting}/`, `schemas/system/`, `providers/crm_api.py`, `evals/` | [flows/crm-agent/](docs/ai/flows/crm-agent/README.md) | `.\venv\Scripts\python.exe -m pytest tests\chatbot` |
| **website-qa**: tra cứu, hỏi đáp trên website | `app/modules/chatbot/{adapters,stages,analysis,orchestration,retrieval,clarification,prompts}/`, `src/chatbot/`, `widget-backend/` | [flows/website-qa/](docs/ai/flows/website-qa/README.md) | `.\venv\Scripts\python.exe -m pytest tests\chatbot tests\api`; trong `widget-backend/`: `npm test` |
| **chat-platform**: phần dùng chung của chat (service key, session, lease, history, trace, health) | `app/{main.py,core,db,api}/`, `app/modules/chatbot/{routers,services,repositories,dependencies.py}`, `sql/` | [flows/chat-platform/](docs/ai/flows/chat-platform/README.md) | `.\venv\Scripts\python.exe -m pytest tests\chatbot tests\api` |
| **doc-ingest**: chunking tài liệu được nạp vào | `app/modules/doc_ingest/` | [flows/doc-ingest/](docs/ai/flows/doc-ingest/README.md) | `..\.venv-ingest\Scripts\python.exe -m pytest tests\doc_ingest` |
| **learning**: học từ hội thoại | `app/modules/learning_ai/` | [flows/learning/](docs/ai/flows/learning/README.md) | `.\venv\Scripts\python.exe -m pytest tests\learning_ai` |

crm-agent, website-qa và chat-platform dùng chung `tests\chatbot`; tool `product_docs_ask`
của crm-agent chạy lại các stage của website-qa. Test nhanh dùng trong lúc làm; trước khi
báo xong phải chạy đủ mục Validation.

Task chạm nhiều luồng hoặc phần dùng chung thì đọc thêm:

| Khi thay đổi | Đọc |
|---|---|
| Route, schema HTTP, SSE event, mã lỗi (kể cả mã lỗi tool CRM ghi trong `tool_errors`) | [api_guidelines.md](docs/ai/api_guidelines.md) |
| Schema input/output của tool agent | README của crm-agent (bảng Tool, Contract) |
| Bức tranh tổng, bảng lớp và trách nhiệm | [architecture.md](docs/ai/architecture.md) |
| Cấu hình, SQL, cờ tính năng, triển khai | [rules/deploy-rules.md](docs/ai/rules/deploy-rules.md) |
| Quyết định liên luồng | [decisions.md](docs/ai/decisions.md) |
| Trạng thái toàn dự án, backlog | [current-state.md](docs/ai/current-state.md) |

## Quy tắc cốt lõi

Tóm tắt; nguồn chuẩn kèm lý do và cách kiểm: [rules/team-rules.md](docs/ai/rules/team-rules.md).

1. Router chỉ làm transport: không gọi LLM provider, không chứa business rule (TR-01).
2. Giữ tách lớp transport, service/stage, provider, repository (TR-02, TR-03).
3. Schema API explicit, versionable; không thay contract bằng `dict` tùy ý (TR-04).
4. Đổi schema, SSE event, mã lỗi hoặc status code thì cập nhật tài liệu và test cùng lúc (TR-06).
5. Secrets lấy từ environment/settings; không commit, không đọc, không in nội dung `.env` (TR-07).
6. Không thêm dependency mới khi chưa hỏi (TR-08).
7. Không sửa module không liên quan; tìm prior art trước khi thêm helper hay abstraction (TR-09).
8. Không mô tả scaffold/stub như tính năng hoàn chỉnh (TR-10).
9. Khi contract hoặc quy tắc tỏ ra sai, dừng và hỏi kèm bằng chứng; không tự làm lệch (TR-12).
10. Tính năng thử nghiệm hoặc chưa có xác thực phải nằm sau cờ cấu hình, mặc định tắt (TR-16).

## Quy trình

1. Đọc tài liệu luồng theo chỉ mục trên. Nếu tài liệu khác code, tin code và báo chỗ lệch.
2. Lập kế hoạch ngắn: module, schema, API, dependency, test bị ảnh hưởng và rủi ro tương
   thích ngược. Hỏi lại khi có lựa chọn hành vi chưa rõ.
3. Thực hiện thay đổi tối thiểu đúng phạm vi.
4. Chạy validation bên dưới.
5. Cập nhật tài liệu: viết lại `STATE.md` của luồng, thêm một mục vào đầu `LOG.md` theo
   mẫu ở [flows/_template/LOG.md](docs/ai/flows/_template/LOG.md); sửa `README.md` khi
   thiết kế đổi. Trạng thái tổng của luồng đổi thì sửa dòng của luồng trong
   `current-state.md`.

## Validation

Từ repository root:

```powershell
npm run lint
npm run build
```

Khi thay đổi backend, từ thư mục `backend`:

```powershell
.\venv\Scripts\python.exe -m pytest tests
```

Khi chỉ sửa tài liệu (`AGENTS.md`, `docs/ai/`, `.claude/rules/`), từ thư mục `backend`:

```powershell
.\venv\Scripts\python.exe scripts\check_ai_docs.py
```

Khi thay đổi `backend/app/modules/doc_ingest/`, từ thư mục `backend` chạy thêm:

```powershell
..\.venv-ingest\Scripts\python.exe -m pytest tests\doc_ingest
```

Nếu virtual environment không tồn tại, báo rõ thay vì tự cài dependency. Báo cáo mọi
validation failure và phân biệt lỗi có sẵn với lỗi do thay đổi gây ra. Lint/build
frontend đạt không phải bằng chứng backend đúng.

## Báo cáo khi xong

Nêu: thay đổi gì, file nào, lệnh validation đã chạy và kết quả, vấn đề còn mở, ảnh hưởng
kiến trúc hoặc contract, việc tiếp theo nếu có.

## Không đọc nguyên file

Các đường dẫn sau lớn hoặc là bản sao; chỉ grep phần cần:

- `.claude/worktrees/`: bản sao cũ của repo, không phải nguồn chuẩn.
- `docs/ai/doc_ingest_spike/output/`, `data/ingest_runs/`: output sinh tự động.
- `docs/ai/tool_instruction/database-structure.sql` (8.587 dòng) và `ai-data-map.md`
  (2.801 dòng): tài liệu của repo CRM bên ngoài.
