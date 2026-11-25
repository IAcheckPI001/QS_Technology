# Nhật ký luồng website-qa

Nhật ký phát triển, **mục mới nhất ở trên**. Chỉ thêm mục mới, không sửa mục cũ; nếu mục
cũ sai, thêm mục mới đính chính. Sau khi thêm mục, viết lại [STATE.md](STATE.md).
Mẫu mục: [../_template/LOG.md](../_template/LOG.md).

Các mục tới 2026-10-29 (nguyên văn từ `current-state.md` và `architecture.md`):
[LOG-archive-2026-11-11.md](LOG-archive-2026-11-11.md). Lịch sử session, service key, lease,
tracing: [chat-platform/LOG.md](../chat-platform/LOG.md).

## 2026-11-26 · Widget: dòng hoạt động AI, nhập bằng giọng nói, nút thêm ảnh (giao diện, chờ backend) (WU-17 đợt 3A) · loại: thay đổi, quyết định

- Quyết định (Toma 2026-11-26): làm giao diện trước; backend (`status`, nhận ảnh) Toma làm sau. Mock duyệt: canvas v83 (W1/W2).
- Thay đổi (chỉ frontend, không thêm thư viện):
  - `src/chatbot/activity/` (`activityModel.js`, `ActivityTimeline.jsx`, `Activity.module.css`): đọc event SSE `status`
    (service `onStatus`), dịch mã bước sang câu vi/en theo ngôn ngữ câu hỏi (quy tắc dấu tiếng Việt), đúng trạng thái và
    hiệu ứng của mock: Đang bắt đầu (≤1,5 s, sau đó về chữ cũ nếu backend chưa phát `status`), từng bước, bộ đếm >3 s, cảnh
    báo >15 s, thu gọn khi có chữ đầu tiên, "✓ Đã xử lý N bước · x giây" bấm mở lại, cảnh báo/lỗi mở sẵn, reduced-motion.
  - **Contract đề xuất** (chưa có backend; backend làm theo hoặc báo lệch): `event: status`, `data: {id, step, state, …}`;
    `step` ∈ security, context, analysis, direct, catalog, retrieval, tool, compose, handoff, clarify; `state` ∈ running,
    done, warn, retry, error, skipped; tuỳ bước: `count`, `docs[]`, `score` (cosine 0–1), `models[]`, `intent`, `target`,
    `turns`, `tool` (crm_schema/crm_query/product_docs_ask), `entities[]` (tên nghiệp vụ), `rows`, `code` (mã lỗi tool).
    Cùng `id` thì cập nhật dòng cũ. Không có chữ hiển thị trong event. Sau khi có backend: ghi vào `api_guidelines.md` (TR-06).
  - Giọng nói: `useSpeechInput` (Web Speech API, vi-VN/en-US theo ngôn ngữ giao diện): chữ vào ô nhập, khách tự gửi; trình
    duyệt không hỗ trợ thì ẩn nút; micro bị chặn thì báo. Chrome gửi âm thanh lên máy chủ Google để nhận dạng.
  - Thêm ảnh: chọn ≤3 ảnh JPG/PNG/WebP ≤5 MB, xem trước, bỏ từng ảnh, ảnh hiện trong tin của khách. **Chưa gửi lên máy chủ**
    (backend chưa nhận) nên sau cờ `VITE_CHAT_IMAGE_INPUT=true`, mặc định tắt (TR-16).
  - Sửa lỗi có sẵn: lịch sử tải xong sau khi khách đã gửi tin thì ghi đè mất tin đó; nay ghép lịch sử vào trước.
- Kiểm chứng: `npm test` → 15 file, 106 đạt (`activity.test.jsx`, `Chatbot.test.jsx` mới); eslint → chỉ lỗi có sẵn
  `ChangeLanguage.jsx`; build đạt. Preview 5174 với luồng SSE giả có độ trễ: bước chạy → ✓ + chip → thu gọn "Đã xử lý 4
  bước · 8,9 giây" → mở lại đủ chi tiết. Nút micro hiện (Chrome).
- Chưa kiểm / mở tiếp: backend phát `status` (Toma); backend nhận ảnh + model đọc ảnh, thời hạn lưu ảnh, kênh nào bật (Toma);
  chưa thử micro thật (cần quyền micro), chưa xem nút ảnh trên trình duyệt (cờ tắt); dòng hoạt động không lưu khi tải lại.
  Chưa commit.

## 2026-11-25 · Mock dòng hoạt động AI của widget (WU-17 đợt 3A) · loại: quyết định, tài liệu

- Quyết định (Toma 2026-11-25): thay "Preparing a reply…" bằng các bước xử lý dễ hiểu, trực quan; trả lời xong thu gọn
  thành một dòng "Đã xử lý N bước · x giây", bấm để mở lại. Chữ do giao diện dịch từ mã bước + số đếm của event SSE
  mới `status` (backend phát ở ranh giới stage/tool), không do LLM sinh; không gửi lập luận, prompt, giá trị dữ liệu CRM.
- Mock: canvas version 81, bảng W1 (website: đang chạy tương tác, đã trả lời thu gọn/mở, không thấy tài liệu, tiếng Anh
  so sánh 2 model) và W2 (CRM: tự sửa truy vấn, đã trả lời, lỗi quyền CRM + tra tài liệu).
- Chưa chốt: hiện tên dữ liệu nghiệp vụ CRM đã đọc; kênh website đủ bước hay 3 bước. Chưa có code.

## 2026-11-25 · Widget giữ nguồn và ảnh sau khi tải lại (WU-17 đợt 2) · loại: thay đổi

- Widget khôi phục `cited_sources` của từng lượt từ `/api/chat/history` (backend ký ảnh mới mỗi lần đọc; chi tiết
  chat-platform LOG cùng ngày), nên huy hiệu có lại "tiêu đề · trang" và ảnh sau khi tải lại. `retriever.py` gắn
  `ChunkHit.similarity` (cosine, chỉ thêm trường; không đổi xếp hạng). File: `src/chatbot/Chatbot.jsx`.
- Kiểm chứng: `npm test` 97 đạt; `pytest tests\chatbot tests\api` đạt. Chưa kiểm với Supabase thật. Chưa commit.

## 2026-11-25 · Widget hiện bảng Markdown và huy hiệu trích dẫn tròn có chú thích (WU-17 đợt 1) · loại: thay đổi

- Vấn đề: prompt trả lời (`prompts/answer.py`) yêu cầu bảng cho thông số/đấu dây nhưng widget dùng `react-markdown`
  không có GFM nên bảng hiện thành chữ `| … |`; `[S1]` là chữ thô, nguồn chỉ có ở danh sách cuối câu trả lời.
- Thay đổi: widget dùng component chung `src/components/Markdown.jsx` (thêm dependency `remark-gfm` ^4.0.1, Toma duyệt
  2026-11-25): bảng cuộn ngang trong khung, bong bóng có bảng dùng hết bề ngang; không render HTML thô; link chỉ http(s).
  `[S#]` → huy hiệu tròn xám; di chuột, chạm hoặc Tab tới thì hiện "tiêu đề · tr. N" lấy từ event `sources` (chú thích gắn
  vào `body` để khung bảng không cắt). Danh sách nguồn cuối câu trả lời dùng cùng số tròn. Chuỗi `chatbot.source`,
  `chatbot.sourcePage` (vi/en). File: `src/chatbot/{Chatbot,SourceList}.jsx`, `Chatbot.module.css`, `src/locales/*.json`;
  test `src/chatbot/SourceList.test.jsx`. Mục đầy đủ: [workspace-ui LOG](../workspace-ui/LOG.md) cùng ngày.
- Kiểm chứng: `npm test` → 95 đạt; eslint file đã sửa → 0; `npm run build` đạt. Preview 5174 + backend thật (kênh website,
  một lượt thật "EtherCAT F54"): huy hiệu ②③ và danh sách nguồn có trang; bảng kiểm bằng luồng SSE giả trong trình duyệt.
- Ảnh hưởng contract/API: không (đọc event `sources` sẵn có).
- Chưa kiểm / mở tiếp: lịch sử tải lại không có nguồn nên huy hiệu chỉ có số, ảnh mất sau tải lại (WU-17 đợt 2: lưu tham chiếu
  ảnh theo lượt, ký lại khi đọc); "Preparing a reply…" chưa thay bằng dòng hoạt động (đợt 3, event `status`); `npm test`
  của `widget-backend/` không chạy (không đổi). Chưa commit.

## 2026-11-21 · Event SSE `sources`: nguồn trích dẫn kèm ảnh có URL ký (D-014, giai đoạn B) · loại: thay đổi

- Vấn đề: ảnh của chunk chỉ là metadata `bucket/path`; chat không trả ảnh, người dùng không thấy hình trong khung chat.
- Quyết định/luật (Toma 2026-11-21, D-014): ảnh trong bucket private `doc-assets`; backend ký URL ngắn hạn theo lượt; model không sinh URL, backend
  đính ảnh của chunk mà câu trả lời trích dẫn (`[S#]`). Event `sources` sau mọi `delta`, trước `done`; sau cờ `CHAT_SOURCES_ENABLED` (mặc định tắt).
  Ảnh thừa hưởng điều kiện của chunk (cờ `RETRIEVAL_APPROVED_ONLY` quyết định có trả chunk draft và ảnh của nó).
- File: `providers/supabase_storage.py` (`AssetSigner`, httpx, ký theo lô một lần mỗi bucket, lỗi chỉ ghi loại lỗi), `sources.py` (`cited_source_ids`,
  `build_sources`), `services/chat_service.py` (`turn_sources`), `routers/sse.py`, `dependencies.py`, `main.py`, `core/config.py` (5 biến mới);
  `src/services/chatbot.service.js` (`onSources`), `src/chatbot/SourceList.jsx`, `Chatbot.jsx`, `Chatbot.module.css`; test `tests/chatbot/test_sources.py`.
- Kiểm chứng: `pytest tests` (venv chính) → 1140 passed, 14 skipped, 1 failed có sẵn (CRLF CSV baseline); event `sources` kiểm qua luồng agent thật với signer giả.
  **Chưa chạy:** `npm test`, `npm run lint`, `npm run build` (worktree không có `node_modules`); chưa xem giao diện trên trình duyệt; chưa ký URL với Supabase thật.
- Ảnh hưởng contract/API/schema/cấu hình: thêm event SSE `sources` ([api_guidelines.md](../../api_guidelines.md)); biến `CHAT_SOURCES_ENABLED`, `SUPABASE_URL`,
  `SUPABASE_SERVICE_ROLE_KEY` (bí mật), `ASSET_URL_TTL_S`, `SOURCE_IMAGES_MAX` ([deploy-rules.md](../../rules/deploy-rules.md)); client cũ bỏ qua event lạ.
- Chưa làm / mở tiếp: ảnh lấy từ `ChunkHit.assets` (chunk cha khi mở rộng) nên nếu hình nằm ở chunk con mà chunk cha không có thì chưa hiện (cần kiểm trên dữ liệu thật);
  màn lịch sử của Workspace chưa hiển thị nguồn/ảnh (URL hết hạn nên cần ký lại khi tải lịch sử); đo `<answer_format>`; widget-backend chưa có test riêng cho event `sources` (chạy `npm test` khi có `node_modules`).

## 2026-11-21 · Đối tượng xem `audience` ở retrieval và prompt định dạng câu trả lời (D-014, giai đoạn A) · loại: quyết định, thay đổi

- Vấn đề: chuẩn bị tài liệu nội bộ chỉ cho CRM. `doc_chunks_v2`/`match_doc_chunks_v2` không có bộ lọc đối tượng xem và
  `Retriever` không biết kênh (một retriever dùng chung website và agent CRM): nạp chunk nội bộ sẽ lộ ra website.
- Quyết định/luật (Toma 2026-11-21): `audience` `public|internal`, mặc định `internal`; website tra `public`, CRM tra cả hai
  (D-014). Ảnh sẽ ở bucket private + URL ký (giai đoạn B, chưa làm). Prompt trả lời thêm `<answer_format>` (danh sách đánh số cho quy trình,
  bảng cho thông số/cổng, cảnh báo ở đầu); chưa đo chất lượng, chưa đổi `PROMPT_VERSION`.
- File: `backend/sql/doc_chunks_v2.sql` (cột `audience`, tham số `p_audiences` mặc định `public`, lọc cả ba nhánh),
  `retrieval/audience.py` (kênh → tập), `schemas/system/retrieval.py` (`RetrievalRequest.audiences`), `orchestration/handlers.py`,
  `stages/execution_stage.py` (lấy kênh từ `state.request_context`), `retrieval/retriever.py` (giao các target cho `fetch_by_ids`),
  `repositories/doc_chunk_v2_repository.py` (truyền `audiences`, coverage chỉ tính chunk public), `prompts/answer.py`;
  test mới `tests/chatbot/test_retrieval_audience.py`, sửa các fake repository.
- Kiểm chứng: `pytest tests` → 1129 passed, 14 skipped, 1 failed có sẵn (CRLF CSV baseline); `pytest tests\doc_ingest` (venv ingest) → 413 passed,
  cùng 1 lỗi có sẵn. Chưa áp SQL trên Supabase, chưa smoke lượt thật.
- Ảnh hưởng contract/API/schema/cấu hình: đổi SQL và chữ ký hàm `match_doc_chunks_v2` (thêm tham số cuối có mặc định); repository
  `match`/`fetch_by_ids` thêm tham số `audiences` (mặc định `public`); không đổi route hay SSE. **Áp SQL trước khi deploy code.**
- Chưa làm / mở tiếp: giai đoạn B (`publish-assets`, bucket private, ký URL, event SSE `sources`, giao diện); coverage `technical_docs` là
  registry chung nên model chỉ có tài liệu nội bộ không được nhận cho kênh CRM (cần registry theo kênh nếu thật sự cần).

## 2026-11-20 · Website cũng chỉ nạp 10 lượt gần nhất làm context (D-015) · loại: thay đổi

- `ContextLoader` dùng chung: lịch sử của phiên website giới hạn `CONTEXT_HISTORY_TURNS` (10) lượt; `Prune` (2.048 token)
  vẫn cắt tiếp như cũ, nên câu trả lời không đổi với phiên ngắn. Chi tiết: [chat-platform LOG](../chat-platform/LOG.md).

## 2026-11-20 · C7: so sánh F86–F54 qua widget đúng cột nhưng thiếu nhiều khác biệt · loại: kiểm chứng

- Phiên `97fa9b85…` 07:29 UTC, pipeline gpt-4o-mini, hạn mức 3 + 2: cắt cột bảng đúng; 7.063 token, 0,00085 USD.
- Câu trả lời chỉ có số trục, màn hình, RTCP, kèm câu "không có tài liệu chi tiết" gây hiểu nhầm: chunk chung lấy
  bảng Compensation (giống nhau) và Multi axis thay General/Hardware. Chi tiết: [crm-agent LOG](../crm-agent/LOG.md)
  mục "Bộ câu so sánh C1–C7". Hướng sửa CMP-1 (chọn bảng có dòng khác nhau) áp chung cho website.

## 2026-11-20 · Câu so sánh: chunk riêng trước chunk chung, cắt cột bảng (D-014, tạm) · loại: thay đổi

- Retriever dùng chung đổi cách chọn chunk khi so sánh: mỗi model 2 chunk riêng, 4 chunk chung (bảng chọn
  model), và bảng markdown chỉ giữ cột của model được hỏi. Mặc định là quyết định tạm D-014.
- Chi tiết và kiểm chứng: [crm-agent LOG](../crm-agent/LOG.md) các mục 2026-11-20. Website cần kiểm câu C7
  (so sánh qua widget) và `run_retrieval_eval.py` trước khi chốt D-014.

## 2026-11-20 · Câu so sánh: hạn mức chunk theo từng model · loại: thay đổi

- Retriever: chế độ `comparison` giữ `RETRIEVAL_COMPARE_PER_MODEL` (mặc định 3) chunk và nhóm ngữ cảnh
  cho mỗi model, thay top-k chung 6 → 5 nhóm (2 model: 6 nhóm; 3 model: 9). Áp cho cả pipeline website.
- Lý do và chi tiết: [crm-agent LOG](../crm-agent/LOG.md) mục 2026-11-20 (Đợt 1 gói E+D).
- Kiểm chứng: `pytest tests` → 1112 passed (test retriever mới). Chưa chạy `run_retrieval_eval.py`
  (cần OpenAI + DB): Toma chạy `dual_source`, `routing_intent` trước khi merge.

## 2026-11-19 · Lượt kiểm thử v2 chưa tới bước tra cứu; đính chính current-state (B-1) · loại: sự cố, kiểm chứng

- Vấn đề: hai lượt kiểm thử sau khi merge PR #3 đều không chạy tra cứu. Lượt 10:12 (kênh crm): server
  chạy checkout chưa pull (`7599b30`, code cũ). Lượt 10:26 (trace `295fa2aa…`, checkout `d2c907e` có v2):
  `llm.chat_tools` 429 `credit_balance_exhausted`, agent 0 bước, `retrieval_status=not_applicable`.
- Kiểm chứng: chạy lại bước khởi động của `main.py` trên Supabase thật, không gọi OpenAI →
  `DocChunkV2Repository`, `approved_only=False`, model `technical_docs` trong DB: F54, F86; coverage
  `[F86]` → `[F54, F86]`; `doc_chunks_v2` active: 356 chunk, đều `draft`.
- Đính chính: mục "Chat chuyển sang doc_chunks_v2" bên dưới quên sửa dòng website-qa trong
  `current-state.md` (vẫn ghi "chat vẫn dùng bảng cũ"); đã sửa.
- Chưa kiểm / mở tiếp: tra cứu v2 trong một lượt thật (span `db.match_doc_chunks`, chunk id thuộc
  `doc_chunks_v2`), chờ nạp credit OpenAI (B-1).

## 2026-11-19 · Chat chuyển sang doc_chunks_v2 (D-009 bước 6) · loại: thay đổi, cấu hình

- Quyết định của Toma: thay hẳn bảng cũ (không có cờ chọn bảng; rollback bằng revert); thêm
  `RETRIEVAL_APPROVED_ONLY` (mặc định `true`); coverage `technical_docs` nạp từ DB lúc khởi động.
- `main.py`: `build_doc_repository()` → `DocChunkV2Repository(MatchV2Options(approved_only=...))`, các option khác
  giữ mặc định production; `load_technical_coverage()` gọi `DocChunkV2Repository.technical_docs_models()` rồi
  `registry.extend_technical_coverage()`; lỗi DB chỉ ghi cảnh báo. Tool `product_docs_ask` dùng chung retriever.
- Xoá `repositories/doc_chunk_repository.py`; `_row`, `_vector_literal` chuyển sang repository v2.
  `backend/sql/doc_chunks.sql` ghi chú không còn được chat dùng.
- Eval giữ nguyên hành vi: `run_retrieval_eval.py` vẫn `approved_only=False` và đủ biến thể; `_patch_coverage`
  và truy vấn model dùng chung code với production; báo cáo ghi thêm `RETRIEVAL_APPROVED_ONLY` của production.
  `run_crm_agent_eval.py`, `compare_agent_models.py` dựng retriever như production.
- Test mới: `tests/chatbot/test_retrieval_v2_wiring.py`.
- Chưa làm: smoke trên Supabase thật; chưa có chunk `approved` nên production mặc định không có tài liệu.

## 2026-11-19 · Tổng hợp baseline định tuyến 120 câu `v1/r0` · loại: đánh giá

- Vấn đề: số tổng hợp trong STATE chưa nêu rõ độ phủ từng nhóm, khác biệt intent với route, và hạn chế của chế độ routing.
- Kết quả: tổng hợp run ngày 14/11 (gpt-4.1-mini, 3 lần, split=all) thành [báo cáo](../../reports/website_qa_routing_eval_v1_r0_2026-11-14.md); tách intent đúng khỏi trường hợp `unknown_product_model` khiến pipeline không tìm.
- Phát hiện tái lập: artifact có 120 câu/R120 nhưng YAML hiện tại chỉ còn 119 câu, không còn R120.
- File: báo cáo mới, `STATE.md`.
- Kiểm chứng: đối chiếu `report.md`, `results.json`, `routing_intent.yaml`; không chạy lại eval.
- Ảnh hưởng contract/API/schema: không.
- Mở tiếp: duyệt bộ câu và đồng bộ lại bộ nguồn với artifact; đo split `test` riêng khi chạy lại.

## 2026-11-16 · Dùng 100milionseek cho eval routing · loại: thay đổi, kiểm thử

- Thêm lựa chọn `--analysis-provider 100milionseek` vào `evals/run_retrieval_eval.py`; provider chỉ được phép
  với `--mode routing`, đọc `HMS_API_KEY` từ môi trường/.env và không thay đổi provider production.
- Chạy R002 với `deepseek-v4.1-flash-free`: bước phân tích thành công, 0 lỗi, độ trễ 12,4–25,6 giây; intent
  `guide.configuration` đúng. Route `no_docs` vẫn sai do đang đo luật `r0`, không phải lỗi API.

## 2026-11-14 · Bàn giao phiên: tổng hợp trạng thái R-1 và vấn đề tồn đọng · loại: tài liệu

- Toma chưa nạp được credit OpenAI → dừng ở đây. Viết lại [STATE.md](STATE.md) làm điểm vào cho phiên sau: bảng tiến
  độ R-1 theo giai đoạn, quyết định đã chốt, kết quả đo, danh sách vấn đề mở (B-1 hết credit, R-1 a–d, R-1a/b/c, C-1,
  C-2, T-1…), lệnh chạy tiếp khi có credit.
- Chép kế hoạch R-1 đã duyệt vào repo: [p3_r1_routing_plan.md](../../reports/p3_r1_routing_plan.md) (trước đó chỉ nằm
  ngoài repo). Cập nhật dòng website-qa, doc-ingest trong `current-state.md`; doc-ingest STATE (catalog chờ verdict,
  `--vi-keywords`, test 376 passed).
- Việc chờ Toma: nạp credit; duyệt `routing_intent.yaml`, `dual_source.yaml`; chọn RT-3 hay RT-3b (+ danh sách
  `non_model_terms` nếu RT-3); quyết `--vi-keywords`; verdict 37 chunk catalog.
- Chưa commit: toàn bộ thay đổi từ catalog `curated/` tới R-1 còn ở working tree (nhánh `feature/deploy_ai_service`).
- Kiểm: `tests` 1120 passed, 14 skipped; `tests\doc_ingest` 376 passed; `check_ai_docs` đạt.

## 2026-11-14 · R-1 giai đoạn B: luật định tuyến có phiên bản (code + test), chưa đo được vì hết credit OpenAI · loại: thay đổi

- **Chặn:** tài khoản OpenAI hết credit (429 `credit_balance_exhausted`) lúc chạy mốc bộ 14 câu, catalog 20 câu, bộ
  "hai nguồn" → ba lượt đó **chưa có số**; mọi phép đo `r1`/`r2` cũng chờ nạp credit. Dịch vụ chat dùng cùng key cũng
  sẽ lỗi cho tới khi nạp. Các lượt đã ghi trước đó (40 câu, 120 câu) có 0 lỗi phân tích nên không bị ảnh hưởng. Eval
  giờ **dừng hẳn** khi bước phân tích lỗi provider (không ghi thành "câu sai").
- A3 (Toma duyệt kế hoạch 2026-11-14): D01 chỉ thêm chunk catalog C0000 vào `acceptable`, giữ `expected` + domain
  `technical_docs` (là phép đo của RT-1); K09 chấp nhận cả hai intent tra catalog (cùng domain, cùng bộ lọc model →
  kết quả tìm y hệt; kênh CRM cũng vậy vì `CatalogLookupStage` chỉ chạy khi không có model).
- A5 nháp `evals/retrieval_cases/dual_source.yaml` (chờ Toma duyệt): 15 câu thông số/đặc điểm F54, F86 có câu trả lời ở
  manual hoặc cả hai nguồn (H01–H15, có gán chunk) + 4 câu đối chứng chỉ-catalog (HC1–HC4).
- Cơ chế: `registry.ROUTING_VERSION = "r0"` (production, không luật), `ROUTING_RULES` (`r1` = RT-1+RT-2+RT-3, `r2` =
  r1+RT-4), `routing_rules()` nhận cả chuỗi thử nghiệm "RT-1+RT-3b". Tham số `routing_version` đi qua
  `resolve_sub_query` → `resolve_with_raw` → `build_analysis` → `AnalysisStage`, `ClarificationResumeStage`. Luật chạy
  ghi `routing_rule:<mã>` vào `warnings`. Eval: `--routing-version`, ghi `meta.routing`.
- Luật (`validate_registry._also_technical` + bước chuẩn hóa model):
  - RT-1: sub-query tra catalog (không phải so sánh) có model có tài liệu kỹ thuật → thêm target `technical_docs`;
    catalog là target chính (`boost` 0,003). Theo điều kiện, không theo tên intent (bao cả `lookup.product_catalog` có
    model: D39, K09).
  - RT-2: câu có mã (`ROUTING_CODE_PATTERN`: `#số`, `CNn`, `Xn`/`Yn`, `ALn`, `Enn`, `Mn`/`Gn`; không khớp RS485, USB2,
    24VDC, mã model) → `technical_docs` là target chính. RT-4 (chỉ `r2`): cụm cấu hình trên câu đã bỏ dấu.
  - RT-3: `REGISTRY["non_model_terms"]` (nháp: 08_RLTR, RBT-01 — chờ Toma duyệt) không phải model lạ.
  - **RT-3b (ngoài kế hoạch, đề xuất thay RT-3):** cụm lạ không có model nào gần giống (`suggest_models` rỗng) không
    phải model lạ. Bằng chứng (thăm dò 12 câu × 3 lần): LLM ghi "08_RLTR", "RBT-01", "driver servo QS", "Yaskawa
    Sigma-7", "Delta VFD-M" vào `unresolved_mentions`, tất cả không có gợi ý; "F84" có gợi ý (F86, F54) nên vẫn hỏi
    lại. Danh sách RT-3 không thể liệt kê hết thiết bị hãng khác.
- Gộp kết quả: `RetrievalTarget.boost`, `RetrievalRequest.boost` (mặc định 0), `handlers.build_retrieval_requests`
  chuyển tiếp, `Retriever._merge` xếp theo `fused_score + boost` (nhánh so sánh giữ round-robin; boost 0 = y như cũ).
  Eval thêm biến thể `sb0.003_tb0`, `sb0.003_tb0.005` (dò điểm cộng target chính).
- R-2 áp vào code: `MatchV2Options` mặc định `scope_mode="boost"`, `scope_boost=0.003` (repository v2, chỉ eval dùng).
  Trong báo cáo eval từ nay `base` = cộng điểm 0,003; hành vi cũ ở biến thể `scope_filter`.
- **Ước tính không gọi LLM** (áp luật lên intent/model LLM đã chọn ở lượt mốc; không ước tính được thứ hạng): 40 câu
  "domain đúng" 0,90 → **1,0**, "đúng cả ba" 0,867 → 0,925 (đổi: D01, D26, D39; còn lại là câu sai nhãn intent nhưng
  đã tìm đúng nguồn: D21, D30, D06); 120 câu "đúng cả ba" 0,936 / 0,942 → 0,975 / 0,961. Ước tính coi mọi hàng "không
  tìm" là được sửa, nên **cao hơn thực tế với `r1`** ("driver servo QS" chỉ RT-3b xử lý). Chưa phải số đo.
- Production không đổi hành vi: `r0` cho kết quả y hệt trước thay đổi (test). Test mới
  `tests/chatbot/test_routing_rules.py` (22); `tests` 1120 passed, 14 skipped.
- Tiếp (khi có credit): mốc 3 bộ còn thiếu; đo `r0`/`r1`/`r2`/RT-3b × 3 lần trên 5 bộ; dò `target_boost`; cổng B.

## 2026-11-14 · R-1 giai đoạn A: công cụ đo định tuyến, bộ câu 120 (nháp), mốc v1/r0 · loại: triển khai, phân tích

- Kế hoạch R-1 (Toma duyệt 2026-11-14), 4 giai đoạn có cổng duyệt: A công cụ đo + bộ câu; B luật định tuyến bằng code
  có phiên bản (`r0` = hiện tại; RT-1 `lookup.product_info` tìm thêm `technical_docs`, RT-2 câu có mã → tài liệu kỹ thuật
  là target chính, RT-3 tên board/phụ kiện không phải model, RT-4 cụm cấu hình); C mô tả intent + khung prompt `v2`
  (tiêu chí: intent chỉ tồn tại khi đổi hành vi; mô tả rút từ nội dung nguồn; câu ranh giới cho cặp dễ nhầm; registry
  là nguồn định nghĩa duy nhất); D so model. Production giữ `v1`/`v1`/`r0` tới khi Toma chốt từng bản.
- A1 `evals/run_retrieval_eval.py`: `--repeat N` (trung bình các lần, **ổn định**, biên "đúng cả ba" giữa các lần),
  `--analysis-model`, `--mode routing` (retriever giả, không tìm), `--split dev|test|all`, bảng nhầm intent, định tuyến
  theo tag, độ trễ p50/p95 + đếm lỗi bước phân tích (không làm dừng eval), `expected_domain` dạng danh sách (một trong
  các domain). Sửa: coverage `technical_docs` chỉ thêm cho model có chunk domain đó (trước thêm nhầm 10S, 10i, 6AH, 6AV,
  F10T). **Chấm chặt hơn:** route `retrieve` mà execution không phát lệnh tìm (sub-query bị
  `planner.held_sub_query_ids` giữ lại) = route sai, ghi "không tìm" → số "route đúng" không so trực tiếp được với các
  báo cáo trước mục này.
- A2 nháp `evals/retrieval_cases/routing_intent.yaml`: 120 câu chỉ chấm định tuyến, 10 nhóm (9 cặp dễ nhầm `cap:…` +
  đối chứng), 72 `dev` / 48 `test`. **Chờ Toma duyệt** (nên thêm câu `test` theo cách hỏi thật).
- Mốc `v1`/`v1`/`r0`, gpt-4.1-mini, 3 lần:
  - 40 câu (`20261114-154614-baseline-v1-r0-diverse40`): đúng cả ba web1 0,867 / web2 0,867; ổn định 0,925 / 0,95; biên
    0,85–0,90 → **nhiễu 2,5–5 điểm %**. Nhầm: D21, D30 → `lookup.product_info` (11/12 lần), D06 → troubleshoot (6/6).
    Không ổn định: D21, D26, D32, D12. Tìm kiếm web2 cộng điểm 0,003: recall@5 0,853 / MRR 0,798. Độ trễ p50 1,4 s,
    p95 1,9 s, 0 lỗi.
  - 120 câu nháp (`20261114-155459-draft-v1-r0-routing120`): đúng cả ba 0,936 / 0,942; ổn định 0,975 / 0,983. Nhóm yếu:
    **`cap:phu_kien` 0,292 / 0,708** — tên board/phụ kiện ("08_RLTR", "RBT-01", cả "Driver servo QS") bị coi là model
    lạ → `unknown_product_model` → không tra cứu (R107, R108, R110, R112–R114): lỗi D26 là **có hệ thống**, không hiếm.
    Còn lại: R008 "công thức tính số xung/mm", R022 "chân X40 là tín hiệu gì", R004 "tham so #12100 la gi" →
    `lookup.product_info`; R104 "phụ kiện" → `lookup.company_info` (2/3 lần). 6 cặp đạt 1,0 ở web1 (lắp đặt↔cấu hình,
    vận hành↔sự cố, công ty↔chuyển người…) → lỗi tập trung ở câu có mã/"là gì" và tên phụ kiện.
- A3 (chưa áp dụng, chờ Toma): D01 chấp nhận thêm chunk catalog C0000 + `expected_domain` cả hai; K09 chấp nhận cả
  `lookup.product_info` và `lookup.product_catalog`; Q12, D39 giữ nguyên.
- Test: `tests/chatbot/test_retrieval_v2.py` thêm 2 test (lặp, ổn định, nhầm intent, split, provider đo giờ, retriever
  giả). `tests` 1097 passed, 14 skipped.

## 2026-11-14 · Gắn phiên bản cho prompt phân tích và mô tả intent (bản hiện tại = v1) · loại: thay đổi

- Lý do (Toma): cần so sánh bản prompt/mô tả intent nào chọn intent tốt hơn (R-1). Lịch sử git: khung prompt đã sửa 3
  lần (pending 10-21; `language`/`model_dependency`/`active_model` 10-29; lọc catalog 11-02), **chưa lần nào nhắm vào
  chọn intent**; mô tả intent (`desc`) vẫn là bản đầu 2026-10-17. Trước đây không có nhãn phiên bản.
- `analysis/prompt/prompt_builder.py`: `PROMPT_VERSION = "v1"` (khung = các khối quy tắc gồm `<intent_rules>` + ví dụ
  mẫu), `_FRAMES`, `build_analysis_prompt(n_examples, version=, intent_desc_version=)`, `analysis_prompt_info()` (phiên
  bản + `n_examples` + sha256 12 ký tự của prompt gửi LLM). `extraction/registry.py`: `INTENT_DESC_VERSION = "v1"`,
  `INTENT_DESC_VARIANTS` (bản thử nghiệm, chỉ ghi intent đổi), `intent_descriptions(version)`.
  `QueryAnalyzer`/`AnalysisStage` nhận hai tham số phiên bản (None = production), `analyzer.prompt_info`, log lúc khởi tạo.
- Không đổi hành vi: prompt sinh ra giống từng byte bản đã commit (so với `git show HEAD`, n_examples None/4/5).
- `evals/run_retrieval_eval.py`: `--prompt-version`, `--intent-desc-version`; báo cáo + `results.json`
  (`meta.analysis_prompt`) ghi nhãn. Kiểm: `data/retrieval_eval/20261114-151457-prompt-v1-check` (K01, K09) → "khung
  `v1`, mô tả intent `v1`, n_examples=4, sha256 `8e431a735a4c`", analysis=gpt-4.1-mini.
- Test mới `tests/chatbot/test_analysis_prompt_version.py` (5): ghim dấu nội dung từng phiên bản (sửa tại chỗ mà không
  tăng phiên bản → đỏ), bản thử nghiệm chỉ đè intent liệt kê, phiên bản lạ bị từ chối. `tests` 1095 passed, 14 skipped.
- Còn mở: (1) công cụ eval thêm coverage `technical_docs` cho mọi model có chunk trong `doc_chunks_v2` kể cả model chỉ
  có chunk catalog (10S, 10i, 6AH, 6AV, F10T) — chưa ảnh hưởng bộ câu hiện tại, cần lọc theo domain trước khi thêm câu
  hướng dẫn cho các model đó; (2) trace production chưa ghi phiên bản prompt (mới có log); (3) đề xuất tiêu chí xác
  định intent + cách đo (chạy lặp, so model) đã gửi Toma, chờ quyết định trước khi soạn `v2`.

## 2026-11-14 · Nạp catalog 7 bộ điều khiển + eval catalog 20 câu, hồi quy 14/40 câu · loại: triển khai, phân tích

- Toma đồng ý nạp: `load_ingest_run --apply` 37 dòng `product_catalog` (`qs_product_catalogue` / `2026-11-14`, draft,
  có embedding) vào `doc_chunks_v2`.
- Bộ câu mới `evals/retrieval_cases/catalog_f54_astro.yaml` (K01–K20; thông số, so sánh, "model nào có RTCP /
  Mechatrolink", giá trị đã chốt C-xx, model mới 10S/10i, không dấu, tiếng Anh). Kết quả
  `data/retrieval_eval/20261114-142557-catalog`: định tuyến đúng cả ba 0,95 (K09 "trọn bộ hệ thống của F54" →
  `lookup.product_catalog`, vẫn đúng domain); tìm kiếm web2 recall@5 **1,0** / MRR **0,839**, web1 0,95 / 0,804, core
  0,9 / 0,747. Hạng thấp: K19 "Số hệ tọa độ chương trình tối đa" (4–9), K10 "quản lý tuổi thọ dao" (4–5) — câu tiếng
  Việt, chunk bảng chọn chỉ có nhãn tiếng Anh như in ("Max.Number Of Program Coordinate", "Tool-life management") →
  ứng viên đo `--vi-keywords` / làm giàu.
- Hồi quy (cùng code, có catalog): bộ 40 câu `20261114-143132-diverse40-catalog` web2 cộng điểm 0,003: 0,853 → 0,824 do
  D26 (hạng 1 → không tìm) — chạy lại D26 riêng (`…-d26-recheck`): hạng 1 → **dao động LLM**, không do catalog. Bộ 14
  câu `…-sample14-catalog`: không đổi (Q13 3 → 2). D02, D13, D15 (tư vấn/so sánh) nay có dữ liệu catalog thật.
- R-1 xác nhận trên dữ liệu thật: D21 (#12100), D30 (không dấu) vẫn bị xếp `lookup.product_info` → giờ **nhận chunk catalog
  (sai)** thay vì rỗng → fallback "khi rỗng" không cứu; cần luật/fallback theo kế hoạch R-1.
- Quan sát mới (chờ kiểm): lần D26 lỗi, bước phân tích đưa "08_RLTR" vào `unresolved_mentions` → hỏi lại
  `unknown_product_model` và **không tra cứu** dù đã có F54 (clarification không chặn nhưng không có lệnh tìm) — ghi để
  kiểm ở R-1.

## 2026-11-14 · Registry: thêm model 10S, 10i (catalog QS) · loại: thay đổi

- `extraction/registry.py`: `product_models` + `10S`, `10i` (ASTRO 10S, ASTRO 10i trong catalog QS; Toma 2026-11-14).
  Tên chuẩn model đang được CRM chuẩn hóa → tạm: alias "Astro 10S" → 10S, "Astro 10i" → 10i; `display_names` "Astro
  10S", "Astro 10i". `ambiguous_aliases`: bỏ "10i", "Astro 10i" (trước trỏ 10iV/10iVE); "Astro 10" và "Astro" thêm 10S,
  10i. `capabilities`: 10S pulse_train+ethercat, 10i pulse_train+ethercat+mechatrolink (bảng chọn catalog trang 6–7).
  `coverage.product_catalog` + 10S, 10i (giữ 10iV theo Toma).
- Ảnh hưởng hành vi: khách gõ "10i"/"Astro 10i" → model 10i, không hỏi lại giữa 10iV/10iVE; tìm theo tiêu chí trả thêm
  10S/10i ("EtherCAT" 9 → 11 model; "EtherCAT, không Mechatrolink" 3 → 4 model → `ask_selection` thay `lookup_each`);
  báo cáo CRM (`reporting/datasets/tickets.py`) nhận product_name "10S"/"10i" là model hợp lệ. Prompt phân tích và schema
  strict lấy danh sách model từ registry (tự cập nhật).
- Đồng bộ `doc_ingest/profiles/registry_snapshot.json`. Test cập nhật: `test_product_catalog.py`,
  `test_catalog_lookup_tool.py`, `test_crm_catalog_flow.py` (kịch bản 3 model dùng fixture tạm gán 10S có Mechatrolink),
  `test_report_validate.py` (alias mơ hồ dùng "Astro 10"). `tests\chatbot` 597 passed.
- Catalog: 37 chunk `product_catalog` (7 bộ điều khiển) đã sinh, chưa nạp (doc-ingest LOG cùng ngày).

## 2026-11-14 · Chốt scope cộng điểm 0,003 (R-2) · loại: quyết định

- Toma chốt **scope cộng điểm, mức 0,003** (vùng tốt đã dò 0,003–0,005), thay lọc cứng. Căn cứ:
  - Dò mức (mục 2026-11-13 dưới), web2 trung bình 3 bộ: lọc 0,807 / 0,736 → 0,003: **0,856 / 0,803**; bộ 8 câu scope
    MRR 1,0 (lọc 0,938); từ 0,007 mất 1 câu ở bộ 40 câu.
  - Eval 40 câu đa dạng (`20261113-180934-diverse40`): định tuyến đúng cả ba 0,875 (sai D21, D30 → product_info;
    D06 → troubleshoot; D01/D39 nhãn mơ hồ). Tìm kiếm web2 lọc 0,735 / 0,673 → cộng điểm 0,003 **0,853 / 0,798**;
    cứu D04, D06, D33 (hạng 1), D09 (4), D12, D22. Khách hàng recall@5 0,667 → 0,867; nhân viên 0,789 → 0,842.
- Đánh đổi đã biết: khi intent đúng (core), lọc vẫn tốt hơn ở S8 (1,0 vs 0,887); định tuyến LLM dao động giữa các lần
  chạy (lọc 40 câu 0,735 rồi 0,706) → đo lại khi bộ định tuyến chuẩn hơn (R-1).
- Chưa đổi code: `MatchV2Options` vẫn mặc định `filter`; đổi mặc định sang `boost` 0,003 (và biến thể `scope_filter`
  trong eval) làm cùng kế hoạch R-1; Settings cho website khi chuyển sang v2 (bước 6).
- Tiếp: R-1 — trước tiên rà soát độ phủ intent/trường trích xuất ↔ chunk hiện có (Toma yêu cầu), rồi mới sửa luật
  code (có phiên bản), fallback khi kết quả yếu, mô tả intent.

## 2026-11-13 · Dò mức điểm cộng scope (0,001–0,01) trên 3 bộ câu · loại: phân tích

- Eval thêm `--scope-sweep` (biến thể: lọc, bỏ qua scope, cộng điểm 0,001/0,002/0,003/0,005/0,007/0,01). Chạy 14 câu,
  8 câu scope, 40 câu: `data/retrieval_eval/20261113-182431-sweep_sample_f54_f86`, `…182602-sweep_scope_f54`,
  `…183217-sweep_diverse_40`.
- Web2 (recall@5 / MRR; trung bình 3 bộ): lọc 0,807 / 0,736; bỏ scope 0,856 / 0,751; 0,001 0,856 / 0,783; 0,002
  0,856 / 0,776; **0,003 và 0,005: 0,856 / 0,803** (cao nhất); 0,007 và 0,01: 0,846 / 0,803 (mất 1 câu ở bộ 40 câu).
  Bộ 8 câu scope: 0,001–0,002 MRR 0,917, từ 0,003 trở lên 1,0. → vùng tốt **0,003–0,005**.
- Core (giả lập intent đúng): bộ 8 câu scope lọc 1,0 / 1,0, mọi mức cộng điểm 0,875 / 0,887 (S8: chunk lỗi chỉ phân
  biệt được bằng scope; cộng điểm không đủ kéo lên) → khi intent đúng, lọc vẫn tốt hơn; khi intent sai (thực tế web),
  cộng điểm tốt hơn.
- Lưu ý dao động: web2 lọc trên 40 câu lần này 0,706 (lần trước 0,735) — định tuyến LLM khác nhau giữa các lần chạy.

## 2026-11-13 · Eval 40 câu đa dạng (khách hàng + nhân viên): định tuyến chưa chuẩn → lọc scope cứng làm trượt · loại: phân tích

- Bộ câu `evals/retrieval_cases/diverse_40.yaml` (Claude soạn theo yêu cầu Toma, chờ duyệt): D01–D20 khách hàng
  (web), D21–D40 nhân viên tra tài liệu hỗ trợ khách (cấu hình, tư vấn, lỗi). Gồm câu không dấu, tiếng Anh, có mã
  (#12100, M1950, Y41, CN9), không nêu model, F86, so sánh, tư vấn sản phẩm, giá/bảo hành, chào hỏi. Chunk đúng xác
  định theo số mục trên `eval-m`; 7 câu chỉ chấm định tuyến. Eval mở rộng: câu không có chunk đúng chỉ chấm định tuyến;
  `expected_route`, `expected_domain` riêng từng câu. Kết quả `data/retrieval_eval/20261113-180934-diverse40`.
- **Định tuyến** (2 lượt như nhau): intent 0,925 · route 1,0 · domain 0,9 · đúng cả ba 0,875. Sai: D21 "tham số #12100
  là gì" và D30 (không dấu, tốc độ G00) → `lookup.product_info` (R-1: câu có mã/câu cấu hình không dấu bị xếp tư vấn
  sản phẩm); D01 (điện áp nguồn) → product_info (nhãn chấp nhận 2 intent nhưng domain kỳ vọng tài liệu kỹ thuật — cần
  Toma xem); D39 (board I/O link) → `lookup.product_catalog` (nhãn mơ hồ); D06 ("mất điện, chạy tiếp chương trình")
  → `troubleshoot.error` thay vì `guide.operation`. Đúng: 3 câu không nêu model hỏi lại (lượt 1), tư vấn/so sánh →
  catalog, giá/bảo hành → handoff, chào hỏi → chitchat.
- **Tìm kiếm**:

| Biến thể | web2 recall@5 | web2 MRR | web1 recall@5 | core recall@5 / MRR |
|---|---|---|---|---|
| lọc scope (base) | 0,735 | 0,673 | 0,735 | 0,971 / 0,88 |
| bỏ qua scope | **0,853** | **0,81** | 0,794 | 0,971 / 0,88 |
| cộng điểm 0,003 | **0,853** | 0,798 | 0,794 | 0,971 / 0,88 |
| cộng điểm 0,01 | 0,824 | 0,797 | 0,765 | — |
| nhánh mã (core) | — | — | — | 0,971 / **0,911** |

  - Lọc cứng trượt khi **intent sai hoặc scope của intent hẹp**: `troubleshoot.error` → chỉ scope `maintenance` (F54
    mới 2 lá có) → D04 (đấu nút START), D06 (chạy tiếp sau mất điện), D33 (màn hình lịch sử lỗi, nhãn `operation`)
    không tìm thấy; fallback chỉ chạy khi rỗng nên không cứu. D09 (wifi xếp `guide.installation`) hạng 11 → bỏ scope 1.
    Cộng điểm 0,003 cứu D04, D06, D33 (hạng 1), D09 (4), D12, D22.
  - Gộp với bộ 8 câu scope (I-46): cộng điểm 0,003 = 1,0 / 1,0 (lọc 1,0 / 0,938; bỏ qua 1,0 / 0,833) → **cộng điểm
    0,003 cân bằng tốt nhất** giữa hai bộ (giữ được phân biệt khi intent đúng, không mất câu khi intent sai). Chờ Toma.
  - Theo người hỏi (web2 lọc → cộng điểm 0,003): khách hàng recall@5 0,667 → 0,867; nhân viên 0,789 → 0,842.
  - Nhánh mã lần đầu có tác dụng (core MRR 0,88 → 0,911: D22 2→1, D35 2→1, D21 10→8) nhưng chunk chỉ khớp mã vẫn thua
    chunk khớp cả vector + FTS (D21 hạng 8) → trọng số mã cần > 1 nếu bật (đo sau).
  - D08 (chỉnh ngày giờ): lượt 1 hạng 1, lượt 2 hạng 12 cùng intent — câu hỏi do bước phân tích viết lại khác nhau giữa
    hai lượt (ngữ cảnh hội thoại) → kéo về các thủ tục "cài tham số" chung (dao động viết lại câu, ghi để đo lặp).
- Từ `backend/`: `pytest tests` → 1077 passed, 14 skipped.

## 2026-11-13 · Trạng thái phương án scope sau I-46 · loại: quyết định

- (1) **Duyệt**: giữ I-46 (scope theo nội dung, `eval-m` đã nạp); `CP-I46` giữ để đối chiếu.
- (2) **Chưa chốt** lọc cứng hay cộng điểm: bộ trích xuất/điều phối (bước phân tích) chưa chắc chính xác hoàn toàn →
  cần đo thêm với bộ câu hỏi đa dạng (khách hàng + nhân viên tra cứu để hỗ trợ khách: hướng dẫn cấu hình, tư vấn sản
  phẩm, khắc phục lỗi). Production dự kiến vẫn `filter` cho tới khi chốt.
- (3) Siết luật `maintenance` (B0175): chưa làm, chờ sau khi đo bộ câu hỏi đa dạng.
- Tiếp: Claude soạn 40 câu đa dạng → chạy eval → đánh giá.

## 2026-11-13 · I-46 nạp lại + đo: scope theo nội dung đạt; lọc cứng có lợi khi nhãn đúng · loại: triển khai

- Toma duyệt bảng scope (`eval-m`); nạp lại `doc_chunks_v2` bằng loader: F54 thay 296/296 (`--embed-parents`), F86
  thay 23/23; đủ embedding, 150/150 `parent_id`. Checkpoint khôi phục: `data/checkpoints/CP-I46/` (nạp lại `eval-l`).
- Đo (`--label i46`): `data/retrieval_eval/20261113-175122-i46` (14 câu), `20261113-175232-i46_scope` (8 câu scope).
  So với mốc trước I-46 (`20261113-172639`, `20261113-173701-scope_test`):

| Bộ câu · biến thể (web2) | recall@5 trước → sau | MRR trước → sau |
|---|---|---|
| 14 câu · lọc scope (base) | 0,643 → **0,714** | 0,521 → **0,600** |
| 8 câu scope · lọc scope | 0,75 → **1,0** | 0,757 → **0,938** |
| 8 câu scope · bỏ qua scope | 1,0 → 1,0 | 0,833 → 0,833 |
| 8 câu scope · cộng điểm 0,003 | 1,0 → 1,0 | 0,817 → **1,0** |

  - 14 câu web2: Q2 không tìm thấy → hạng 2; Q5 3 → 1; không câu nào trong top 5 bị tụt; Q10 8 → 14 (vẫn ngoài ngữ
    cảnh cả trước và sau — gốc là thuật ngữ "đo dao"; chunk soft limit/so dao vừa có `configuration` chen lên).
  - 8 câu scope, core (giả lập phân tích chọn đúng intent): lọc 1,0 / 1,0; bỏ qua scope 0,875 / 0,761 (S8 hạng 11);
    cộng điểm 0,875 / 0,887 (S8 hạng 10). Web2: lọc S8 hạng 2 vì **B0175 (quy trình M100) được gán thêm
    `maintenance`** (luật "reports an error" — điểm Claude đã nêu cần xem) và đứng trên chunk lỗi B0177.
- Kết luận: I-46 **đạt** (không quay lại CP-I46). Khi nhãn đúng, **lọc scope có lợi rõ** so với bỏ qua scope (S3, S7,
  S8); cộng điểm 0,003 ngang lọc ở web, kém lọc ở core. Đề xuất: giữ `filter`; siết luật `maintenance` (bỏ "reports
  an error" đứng riêng, chỉ giữ "the cause is/of", troubleshoot + loại `alarm`) để B0175 không thành chunk bảo trì.

## 2026-11-13 · THỬ NGHIỆM: scope có giúp chọn đúng phần không (I-46/R-2) · loại: thử nghiệm

Bản kiểm thử (Toma yêu cầu) để xác định scope có giúp xác định rõ hơn và cải thiện chất lượng không. Không sửa luật
chunking, không ghi DB; nhãn scope trong `doc_chunks_v2` giữ nguyên (gán theo phần tài liệu).

- Thống kê nhãn (script thử nghiệm, luật từ khóa thô theo tiêu đề mục + nội dung; chỉ là chỉ báo):
  `data/retrieval_eval/scope_test/scope_audit_f54.md` — 138/243 lá lệch; thiếu `configuration` 85 (hiện 34, theo nội
  dung ≈ 119), thiếu `operation` 47 (một phần là nhiễu: thủ tục cài tham số có "press", "screen"), thiếu `maintenance`
  21, thừa `installation` 55.
- Bộ câu thử `evals/retrieval_cases/scope_f54.yaml` (8 câu, cùng chủ đề khác loại công việc; chunk đúng + intent do
  Claude gán, chờ Toma duyệt): về home — S1 đấu cảm biến (installation), S2 cài tốc độ, S3 cài kiểu DOG/INDEX
  (configuration), S4 chạy Auto home (operation); bộ so dao — S5 đấu dây (installation), S6 cài tọa độ
  (configuration), S7 quy trình M100 (operation), S8 lỗi (maintenance). Eval: câu mang `scopes` đúng của nó (core lọc
  theo scope đó = giả lập phân tích chọn đúng intent); biến thể `scope_none` (bỏ qua scope), `scope_boost0.003/0.01`;
  báo cáo ghi scope hiện tại của chunk mong đợi; `--label` cho thư mục kết quả.
- Kết quả `data/retrieval_eval/20261113-173701-scope_test`: định tuyến 8/8 đúng. Tìm kiếm:
  - **Không cần scope** (câu tự phân biệt bằng từ ngữ): S1, S2, S4, S5, S6 hạng 1 ở mọi biến thể — lọc không hại.
  - **Scope có ích khi nhãn đúng**: S8 (chunk lỗi có `maintenance`) — lọc: hạng 1; bỏ scope: hạng 11 (core; các chunk
    "alarm signal wiring", "maintenance screen" chen lên).
  - **Scope có hại khi nhãn sai**: S7 — chunk M100 B0175 chỉ có `installation` → lọc `operation` **không tìm thấy**;
    bỏ scope: hạng 2–3. S3 — chunk mô tả kiểu home B0143/B0146/B0147 chỉ `installation` → lọc `configuration`: hạng
    15 (bảng tham số chiếm top); bỏ scope: hạng 2 nhưng hạng 1 là "3.1 Auto home" (chunk vận hành) — tức không scope
    thì lẫn sang phần vận hành.
  - Tổng (core): lọc recall@5 0,75 · MRR 0,758; bỏ scope 0,875 · 0,761; cộng điểm 0,003: 0,875 · 0,742. Web2: lọc
    0,75 · 0,757; bỏ scope 1,0 · 0,833; cộng điểm 0,003: 1,0 · 0,817.
- Kết luận thử nghiệm: scope **có giá trị phân biệt** (S8; S3 không scope lẫn sang Auto home) nhưng chỉ khi nhãn đúng;
  với nhãn hiện tại lọc cứng làm mất câu (S3, S7) → hướng đã duyệt đúng: sửa I-46 (gán scope theo nội dung, nhiều scope
  khi đúng) rồi đo lại `filter`/`boost`/`none` trên cả 14 câu + 8 câu scope trước khi chốt.

## 2026-11-13 · Bật làm sạch câu FTS; scope giữ lọc cứng; đo song song theo loại câu · loại: quyết định

- Toma: **bật làm sạch câu FTS** (`MatchV2Options.fts_clean` mặc định `True`) nhưng tiếp tục kiểm thử song song với
  câu hỏi đa dạng; **scope giữ `filter`** tới khi sửa I-46, rồi đo lại `filter`/`boost` với câu hỏi phân biệt theo
  scope mới chốt (hướng đã duyệt, chốt sau kiểm thử). Trọng số RRF giữ 1.
- Chỉ ảnh hưởng `DocChunkV2Repository` (eval); retriever của dịch vụ chat (web + agent CRM) vẫn bảng cũ — áp dụng khi
  chuyển sang v2.
- Eval: `base` = mặc định mới; biến thể `no_fts_clean` (đo song song R-4), `scope_boost0.003`/`0.01` (R-2); bỏ biến thể
  giảm trọng số FTS. Báo cáo thêm bảng **theo loại câu (tag)**: recall@5 / MRR cho core/web2 × có/không làm sạch,
  scope boost.
- Mốc `data/retrieval_eval/20261113-172639`: core base recall@1 0,786 · MRR 0,861 (không làm sạch: 0,429 · 0,643);
  web2 base recall@1 0,429 · recall@5 0,643 · MRR 0,521 (không làm sạch: 0,286 · 0,643 · 0,426); web2 scope boost
  recall@5 0,714 · MRR 0,59. Theo tag (core): làm sạch nâng MRR `tu_khoa` 0,312 → 0,762, `dau_day` 0,59 → 1,0,
  `loi_go` 0,25 → 1,0, `kich_thuoc` 0,5 → 1,0; không tag nào giảm. Lưu ý: `core:unaccent` kèm làm sạch thấp hơn base
  (MRR 0,79). Tag `tham_so` yếu ở mọi biến thể (Q5, Q10 — thuật ngữ). Bộ câu hỏi còn thiếu: câu tiếng Anh, so sánh,
  tên nút, phân biệt scope, câu không dấu (mới 1 câu).
- Test: `tests` → 1076 passed, 14 skipped.

## 2026-11-13 · R-4 (làm sạch câu FTS, trọng số RRF) và R-2 (scope cộng điểm): triển khai + đánh giá · loại: thay đổi

- SQL `doc_chunks_v2.sql`: `match_doc_chunks_v2` thêm `vector_weight`, `fts_weight`, `code_weight` (mặc định 1) và
  `p_scope_mode` (`filter` mặc định | `boost`) + `scope_boost` (mặc định 0) — mặc định = hành vi cũ. **Toma áp lại trên
  Supabase 2026-11-13** (DR-04); kiểm: còn một chữ ký v2 (23 tham số), `SET hnsw.*` giữ, dữ liệu 319 dòng.
- Code: `chatbot/retrieval/fts_query.py` (`clean_fts_query`: bỏ model đang lọc, từ chức năng VI/EN có và không dấu,
  cụm "bộ điều khiển", "hướng dẫn", "như thế nào"…; **giữ** "vào", "ra" (đầu vào/đầu ra), "không" (triệu chứng);
  câu sạch rỗng → câu gốc; chỉ nhánh FTS, embedding vẫn câu gốc); `MatchV2Options` thêm `fts_clean`, trọng số,
  `scope_mode`, `scope_boost` (mặc định tắt). Eval: chế độ web chạy bước phân tích **một lần** mỗi câu mỗi lượt rồi
  **phát lại** đúng các lệnh tìm với từng biến thể (so sánh không lẫn dao động LLM). Test `test_retrieval_v2.py` 7.
- Kết quả `data/retrieval_eval/20261113-171149` (14 câu):

| Biến thể | recall@1 | recall@5 | MRR | mong đợi @1 |
|---|---|---|---|---|
| core: base | 0,429 | 0,929 | 0,643 | 0,357 |
| **core: fts_clean** | **0,786** | 0,929 | **0,861** | **0,571** |
| core: fts_w0.5 | 0,571 | 0,857 | 0,691 | 0,357 |
| core: fts_clean+w0.5 | 0,643 | 0,857 | 0,756 | 0,357 |
| web2: base | 0,357 | 0,643 | 0,473 | 0,286 |
| web2: scope_boost (0,01 / 0,003 như nhau) | 0,357 | 0,714 | 0,494 | 0,214 |
| web2: fts_clean | 0,5 | 0,643 | 0,568 | 0,357 |
| **web2: r2+fts_clean** (boost 0,003 + làm sạch) | **0,571** | **0,714** | **0,637** | 0,357 |

- Đánh giá R-4: **làm sạch câu FTS** sửa đúng gốc — core không câu nào tụt, 5 câu lên hạng 1 (Q9 2→1, Q11 5→1, Q12
  2→1, Q13 4→1, Q14 2→1). **Giảm trọng số FTS có hại**: Q9 2→21 (chunk đúng chỉ FTS tìm ra), Q10 21→26 → không dùng
  (giữ trọng số 1).
- Đánh giá R-2: chế độ boost tìm lại được Q2 (không có → hạng 2–3), Q3 2→1, Q5 4→3, nhưng **Q10 8→23** (12 khi kèm
  làm sạch): bỏ lọc scope cho chunk tổng quan và chunk soft limit cùng chủ đề "giới hạn hành trình" vào ứng viên;
  Q11 4→5, Q13 1→2. Hai mức 0,01 và 0,003 cho cùng hạng chunk đúng trên 14 câu (đã kiểm hàm: điểm cộng có áp dụng).
  Bộ 14 câu chưa có câu phân biệt theo scope → chưa đủ để kết luận boost an toàn; gốc là gán scope (I-46).
- Định tuyến (chạy lại 2 lần): như lần trước (đúng cả ba 0,786); một lần chạy, web1 Q7 không nêu model lại đi
  `retrieve` (LLM coi câu là chung) thay vì hỏi lại — dao động của LLM, ghi để đo lặp sau này.
- Đề xuất (chờ Toma): bật `fts_clean` khi chuyển retriever sang v2; trọng số giữ 1; scope: giữ `filter` tới khi sửa
  I-46, đo lại `filter` và `boost` với câu hỏi phân biệt scope rồi mới quyết.

## 2026-11-13 · Eval 14 câu: nguồn gốc lỗi định tuyến và tìm kiếm · loại: phân tích

Chạy `evals/run_retrieval_eval.py --mode all` → `data/retrieval_eval/20261113-163914` (chỉ đọc DB; `doc_chunks_v2`:
F54 296 + F86 Installation 23, đều draft; không có chunk danh mục sản phẩm).

- **Định tuyến** (lượt 1 và lượt 2 như nhau): intent đúng 0,857 · route đúng 1,0 · domain đúng 0,786 · đúng cả ba
  0,786. Sai domain: Q8, Q9, Q12 → `lookup.product_info` → `product_catalog`.
- **Tìm kiếm**: core recall@1 0,429 · recall@5 0,929 · MRR 0,643 · mong đợi @1 0,357; web lượt 1 recall@5 0,214 (Q1–Q7
  hỏi lại model, đúng thiết kế); web lượt 2 recall@1 0,286 · recall@5 0,643 · MRR 0,426. Các biến thể (mã, bỏ dấu,
  tìm cả cha) vẫn không khác biệt.

Nguồn gốc lỗi (mỗi câu trượt/kém có ít nhất một):

| # | Nguyên nhân | Bằng chứng | Câu | Hướng khắc phục |
|---|---|---|---|---|
| R-1 | Ranh giới intent: câu cách làm/công thức/kích thước/chức năng cổng có model bị xếp `lookup.product_info` (tìm `product_catalog`, không fallback `technical_docs`) | intent product_info ở cả 2 lượt | Q8, Q9, Q12 | Luật code: câu có mã (CN10, #…) hoặc hỏi cách làm/công thức → tìm cả `technical_docs`; fallback `technical_docs` cho product_info; chỉnh mô tả intent ("cổng", "nguyên lý", "kích thước") |
| R-2 / I-46 | Scope là bộ lọc cứng; chunk cài tham số 2.6.4.x chỉ có scope `installation` | `guide.configuration` lọc `configuration` → Q2 không có chunk đúng trong ứng viên; Q5 hạng 4 vì bảng 5.1/5.2 (có `configuration`) chiếm top | Q2, Q5 | Tra cứu: scope là cộng điểm hoặc tìm lại không lọc scope khi ít kết quả; chunking: gắn scope theo nội dung |
| **R-4 (mới)** | Trộn RRF bằng trọng số ngang nhau + FTS dạng OR với từ phổ biến ("bộ điều khiển", "F54", "cách", "đấu") → chunk tổng quan có mặt ở cả hai nhánh (B0000 1.1 Overview, B0001, B0004/B0005 2.1 I/O ports, B0009 2.3 bảng input) thắng chunk đúng chỉ mạnh ở vector | Q11: chunk mong đợi vector hạng 3–4 (0,674, cao hơn mọi chunk sai trong top 5) nhưng không khớp FTS → hạng trộn 13; Q12, Q13, Q14 hạng 1 là chunk tổng quan | Q11, Q12, Q13, Q14 | Đo: trọng số vector/FTS trong RRF, bỏ tên model và từ phổ biến khỏi câu FTS (model đã là bộ lọc), ngưỡng điểm FTS tối thiểu |
| D | Thuật ngữ/làm giàu: người dùng gọi khác tài liệu | Q10 "đo dao" ≠ "bộ so dao" (hạng 21); Q9 "tỷ số truyền điện tử" (đã thêm bảng thuật ngữ, chưa làm giàu lại); Q5 "lần thứ hai" ≠ "2nd"; Q13 lỗi gõ "tính hiệu" | Q5, Q9, Q10, Q13 | Bảng thuật ngữ + prompt v5 + làm giàu lại; thêm cách gọi đồng nghĩa ("đo dao") |
| T | Chunk "mỏng" (chỉ tiêu đề + caption hình): ít chữ cho FTS, tóm tắt VI dễ thiếu từ người dùng gõ | B0082/B0083 sơ đồ servo (Q11) | Q11 | Mô tả ảnh (hướng C, vision) đưa vào `embed_text` — đo ở Bước 4 |
| E | Môi trường đo: v2 chưa có chunk danh mục sản phẩm | Định tuyến sang catalog → 0 ứng viên | Q8, Q9, Q12 | Chỉ ảnh hưởng đo; xử lý khi có chunk danh mục thật |

## 2026-11-13 · Bộ câu hỏi đánh giá thêm Q11–Q14 (14 câu) · loại: thay đổi

- Toma bổ sung: Q11 "Hướng dẫn đấu nối Servo trong bộ điều khiển F54" (mong đợi các sơ đồ 2.6: B0080–B0083), Q12
  "Kích thước bản vẽ lắp của bộ điều khiển F54" (B0002, scope `operation`; intent chấp nhận `guide.installation` hoặc
  `lookup.product_info` — nhưng product_info tìm `product_catalog`, nên câu này kiểm ranh giới intent), Q13 "Cách đấu
  tính hiệu so dao…" (giữ lỗi gõ "tính hiệu"; mọi sơ đồ bộ so dao 2.3.3.x), Q14 "Cách đấu cảm biến về home…" (sơ đồ
  2.3.2.x). Chunk đúng và intent do Claude gán theo `f54/eval-l`. Chưa chạy.

## 2026-11-13 · Xóa bản chép chunk viết tay khỏi v2; duyệt nhãn intent và hướng tối ưu bộ định tuyến · loại: quyết định

- Toma: xóa 3 chunk viết tay đã chép sang v2 (chỉ bản chép; bảng cũ `doc_chunks` giữ nguyên vì retriever của dịch vụ
  chat còn đọc). Đã chạy `load_ingest_run --delete --doc-id <id> --doc-version v1-manual` cho 2 tài liệu: xóa 1 + 2
  dòng; `doc_chunks_v2` còn 319 dòng (F54 296, F86 Installation 23), bảng cũ vẫn 3 dòng.
- Toma duyệt nhãn `expected_intent` của 10 câu mẫu và hướng tối ưu bộ định tuyến (R-1 ranh giới intent, R-2 scope
  lọc cứng, R-3 coverage viết cứng). Bộ định tuyến là bản thiết kế đầu, chưa kiểm thử/tối ưu; 10 câu mới là điểm
  khởi đầu — tối ưu **dần dần** theo câu hỏi đa dạng thực tế của nhân viên và khách hàng (bộ câu hỏi lớn dần, mỗi
  thay đổi đo trước/sau).
- Hệ quả đo: không còn dòng `product_catalog`/`company_info` trong v2 → định tuyến sang danh mục sản phẩm sẽ không có
  dữ liệu để tìm cho tới khi có chunk danh mục thật.

## 2026-11-13 · Eval tách định tuyến / tìm kiếm + lượt 2; chép 3 chunk viết tay sang v2 · loại: thay đổi

- Nguồn lỗi chế độ website (lần chạy trước): (A) eval chỉ giả lập lượt đầu — câu không nêu model bị hỏi lại model
  (đúng thiết kế `model_policy: required`); (B) định tuyến: mô tả intent `lookup.product_info` ("cổng/giao tiếp",
  "nguyên lý") chồng `guide.installation`/`guide.configuration`, intent này không có fallback sang `technical_docs`;
  (C) v2 chưa có dòng `product_catalog`; registry `coverage` viết cứng chỉ F86; (D) chất lượng tìm (thuật ngữ).
- Sửa eval: `evals/run_retrieval_eval.py` thêm chế độ `website_ctx` (người dùng đã nêu model ở lượt trước:
  `active_model` + 2 tin nhắn); chấm định tuyến (intent theo `expected_intent` của câu — nhãn Claude đề xuất, chờ Toma
  duyệt; route mong đợi `clarify` khi câu cần model mà chưa có, `retrieve` khi đã có; domain `technical_docs`).
  Test `test_retrieval_v2.py` 4 → 5.
- Loader thêm `--copy-v1`: chép chunk viết tay của `doc_chunks` sang v2 (`source=manual`, `doc_version=v1-manual`,
  giữ embedding, khóa `<doc_id>:M<index>`, chạy lại không trùng). **Đã chạy (Toma đồng ý)**: 3 dòng (F86 spec
  `product_catalog`, giới thiệu công ty `company_info`); lần hai chép 0. Lưu ý: `doc_id f86_installation_2024-04-25` giờ
  có 2 phiên bản trong v2 → xóa phải kèm `--doc-version`.
- Kết quả `data/retrieval_eval/20261113-161427`:
  - **Định tuyến** (`website` và `website_ctx` như nhau): intent đúng 0,8 · route đúng 1,0 · domain đúng 0,8. Sai: Q8
    ("Cổng CN10 … dùng để làm gì?"), Q9 ("công thức tính tỷ số truyền điện tử") → `lookup.product_info` →
    `product_catalog`. Lượt đầu Q1–Q7 hỏi lại model đúng như mong đợi.
  - **Tìm kiếm**: core như lần trước (recall@5 0,9); `website_ctx` recall@1 0,4 · recall@5 0,6 · MRR 0,487 · trong
    ngữ cảnh 0,6. Ngoài Q8/Q9 (định tuyến) và Q10 (hạng 8): **Q2 định tuyến đúng mà không tìm thấy** — intent
    `guide.configuration` lọc scope `configuration`, chunk 2.6.4.7 chỉ có scope `installation` (F54: 34/243 lá có
    `configuration`; mục cài tham số 2.6.4.x phần lớn chỉ `installation`). Nguyên nhân thứ năm: **(E) scope là bộ lọc
    cứng mà gán scope ở chunking chưa khớp cách router chia intent**.
- Từ `backend/`: `.\venv\Scripts\python.exe -m pytest tests` → 1074 passed, 14 skipped.

## 2026-11-13 · Công cụ đánh giá tra cứu + chạy 10 câu mẫu trên `doc_chunks_v2` · loại: thay đổi

- Code mới: `chatbot/repositories/doc_chunk_v2_repository.py` (`DocChunkV2Repository` + `MatchV2Options`, cùng giao
  diện với `DocChunkRepository`; mặc định = hành vi production dự kiến: chỉ approved, không tìm cha); `chatbot/
  retrieval/codes.py` (`extract_codes`, cùng luật chuẩn hóa với adapter doc-ingest); `ChunkMatch` thêm trường tùy
  chọn `chunk_key`, `chunk_role`, `chunk_type`, `code_score`, hạng từng nhánh. Retriever của dịch vụ chat **chưa đổi**
  (vẫn bảng cũ).
- `evals/run_retrieval_eval.py`: chế độ `core` (bộ lọc cố định, `Retriever` thật, biến thể base/codes/unaccent/
  codes+unaccent/parents) và `website` (`RetrievalPipeline` thật; coverage technical_docs của model đã nạp được thêm
  **trong bộ nhớ tiến trình**). Chỉ đọc DB; `p_approved_only = false`. Bộ câu hỏi `evals/retrieval_cases/
  sample_f54_f86.yaml` (Toma duyệt Q1–Q8, đổi Q2 sang bước vít me, thêm Q9–Q10). Kết quả `data/retrieval_eval/`
  (gitignore). Test `tests/chatbot/test_retrieval_v2.py` (4).
- Kết quả `data/retrieval_eval/20261113-155833`: **core** base recall@1 0,6 · recall@5 0,9 · MRR 0,755 · mong đợi @1
  0,5 · trong ngữ cảnh 0,9; biến thể không khác biệt đáng kể (chỉ Q8 có mã và đã hạng 1; bỏ dấu làm Q9 2→3; tìm cả cha
  không đổi) → 10 câu chưa đủ để quyết các điểm "Đ". Trượt: **Q10** "tham số giới hạn hành trình đo dao tự động" hạng
  21 (chunk soft limit chiếm top; "đo dao" ≠ "bộ so dao"); Q9 "tỷ số truyền điện tử" chunk mong đợi hạng 5, vector
  0,436 (tóm tắt VI viết "tỉ số bánh răng điện tử"); Q5 chunk tham số Homing Feedrate **1st** hạng 1 ("lần thứ hai" ≠
  "2nd"); Q3 hạng 1 là B0096 "2.6.4.3 Software limit" (có thể cũng đúng → Toma xem lại nhãn).
- **website**: recall 0 — Q1–Q7 không nêu model → analysis `route=clarify` (hỏi lại model; đúng thiết kế
  `model_policy`), chưa tới bước tìm; Q8, Q9 bị xếp intent `lookup.product_info` → tìm `product_catalog`, không tìm
  tài liệu kỹ thuật; Q10 `guide.configuration` → hạng 8, ngoài top 6.
- Từ `backend/`: `.\venv\Scripts\python.exe -m pytest tests` → 1072 passed, 14 skipped.

## 2026-11-13 · Nạp F54 + F86 Installation vào `doc_chunks_v2` (Cổng 2) · loại: triển khai

- Toma đồng ý nạp. `load_ingest_run --apply --embed-parents` cho `f54/eval-l` (296 dòng: 150 con, 53 cha, 93 độc lập;
  embed cả cha để đo biến thể "tìm cả cha") và `--apply` cho `f86_italliation/eval-l` (23 độc lập). Tất cả `draft`.
  Embedding `text-embedding-3-small` ≈ 0,0022 USD.
- Kiểm (`inspect_doc_chunks.py --table doc_chunks_v2`): mọi dòng có embedding; 150/150 con có `parent_id`; 0 liên kết
  cha hỏng; 177 + 11 dòng có `codes`; bảng 8 MB. Bảng `doc_chunks` cũ không đổi. Rollback: `load_ingest_run --delete
  --doc-id <doc_id>`.
- Thử tìm (chỉ đọc, `p_approved_only => false`, model F54; ví dụ lẻ, chưa phải đo): "Cách đấu dây báo lỗi servo loại
  PNP?" → B0040 hạng 1 (vector 0,686); "Tham số #12010 dùng để làm gì?" với `p_codes = {#12010}` → B0111 (chunk có
  "#12010 = 1") lên hạng 1 nhờ nhánh mã (vector hạng 14, FTS hạng 13); câu không dấu "cach cai dat gioi han hanh trinh
  mem soft limit" → B0161 hạng 1 khi tắt bỏ dấu, hạng 4 khi bật. `vector_score` của chunk đúng 0,45–0,69 (ngưỡng
  `min_similarity` hiện 0,25). Không chunk cha nào được trả (mặc định).
- Tiếp: công cụ đánh giá `evals/run_retrieval_eval.py` (chế độ core + website); bộ câu hỏi chờ Toma.

## 2026-11-13 · Loader `doc_chunks_v2` sẵn sàng (chưa nạp) · loại: thay đổi

- `app/modules/chunking_loader/load_ingest_run.py` nạp `build/doc_chunks_v2.jsonl` của luồng chunking vào
  `doc_chunks_v2` (kiểm model theo registry, embed lá trước, một transaction, gán `parent_id`). Chi tiết, số liệu
  dry-run: doc-ingest LOG cùng ngày. Chưa ghi DB (Cổng 2).

## 2026-11-13 · Áp `doc_chunks_v2.sql` lên Supabase (Cổng 1) · loại: triển khai

- Toma dán và chạy `backend/sql/doc_chunks_v2.sql` trong SQL editor của Supabase, thành công (DR-04: áp ngày
  2026-11-13).
- Kiểm bằng `scripts/inspect_doc_chunks.py --table doc_chunks_v2` (chỉ đọc): bảng có đủ 40 cột (`embedding`
  vector(1536); `fts`, `fts_unaccent` generated), 14 ràng buộc, 13 index (10 tạo mới + khóa chính + 2 unique);
  `match_doc_chunks_v2` đúng chữ ký, có `SET hnsw.iterative_scan = relaxed_order`, `hnsw.ef_search = 100`;
  `unaccent` 1.1 ở schema `extensions`; `immutable_unaccent` là IMMUTABLE; 0 dòng; `doc_chunks` cũ vẫn 3 dòng.
- Gọi thử (transaction READ ONLY): hàm chạy với tham số mặc định và với mọi tham số bật (bảng rỗng → 0 dòng);
  `immutable_unaccent('Đấu dây báo lỗi servo, cài đặt dầu')` → "Dau day bao loi servo, cai dat dau" (xác nhận rủi ro
  "đấu"/"dầu" cùng thành "dau" — đo ở Bước 4); `websearch_to_tsquery('simple', '#12010 X41')` → `'12010' & 'x41'`
  (xác nhận S-02: FTS bỏ `#`).
- Chưa nạp dữ liệu (Cổng 2 sau bước 3b, 4).

## 2026-11-13 · SQL `doc_chunks_v2.sql` (bước 3a, chưa áp) · loại: thay đổi

- File mới `backend/sql/doc_chunks_v2.sql` (idempotent): extension `unaccent` (schema `extensions`; `vector` đã ở
  `public`), hàm `immutable_unaccent`, bảng `doc_chunks_v2` 40 cột theo §10 của
  [p2_doc_chunks_schema_review.md](../../reports/p2_doc_chunks_schema_review.md) (check: con có cha, lá có embedding,
  có embedding thì có `embedding_model`; không check danh sách model), 10 index, hàm `match_doc_chunks_v2` (lọc
  giống nhau mọi nhánh, `[]` = không lọc — sửa E-05; `p_approved_only` mặc định bật; chỉ tìm lá trừ khi
  `p_include_parents`; nhánh vector `hnsw.iterative_scan = relaxed_order`, `ef_search = 100`; FTS có/không bỏ dấu;
  nhánh mã; RRF 3 nhánh + `spec_boost` + `type_boost`; trả thêm khóa, vai trò, loại, trang in, điểm và hạng từng nhánh).
- `scripts/inspect_doc_chunks.py`: thêm `--table doc_chunks_v2`, schema của extension, kiểm liên kết cha.
- **Chưa áp lên Supabase** (Cổng 1); chưa kiểm cú pháp trên Postgres thật (repo không có Postgres cục bộ).
  `deploy-rules.md` thêm dòng 6 cho file này.

## 2026-11-13 · D-009: bảng `doc_chunks_v2`, retriever chỉ dùng chunk approved · loại: quyết định

- Toma duyệt các điểm "C" của đề xuất, tạo bảng mới `doc_chunks_v2` song song bảng cũ, và quy tắc retriever chỉ dùng
  chunk `review_status = approved` (tham số `p_approved_only`, Settings `RETRIEVAL_APPROVED_ONLY` mặc định bật; đánh
  giá được tắt). Danh sách 40 cột, cách đo bỏ dấu, định nghĩa `approved`:
  [p2_doc_chunks_schema_review.md](../../reports/p2_doc_chunks_schema_review.md) §10–§12; sổ: D-009.
- Chưa đổi SQL trên Supabase, chưa đổi code.

## 2026-11-13 · Kiểm `doc_chunks` trên Supabase thật + đề xuất bảng/hàm v2 · loại: phân tích

- Toma: Supabase chỉ một môi trường, chưa có người dùng thật, `doc_chunks` có 3 chunk thử; bảng/hàm là bản thiết kế
  trước, cần đánh giá lại trước khi nạp chunk từ luồng chunking.
- Script mới `backend/scripts/inspect_doc_chunks.py`: chỉ đọc (transaction READ ONLY), in cột, ràng buộc, index, định
  nghĩa hàm, extension, số dòng. Windows cần `WindowsSelectorEventLoopPolicy` cho psycopg async.
- Kết quả: Postgres 17.11, pgvector 0.8.2 (iterative scan có, đang tắt), `unaccent` chưa cài; 3 dòng thử đều không
  phải `technical_docs`. Lệch repo ↔ DB: `embedding` nullable; check `product_models` còn ASTRO_* (chưa áp
  `migrate_product_models_crm.sql`); `match_doc_chunks` thật dùng `p_models is null` ở **cả hai nhánh** → `[]` trả
  rỗng toàn bộ (E-05 nặng hơn ghi chép).
- Đề xuất v2 (bảng `doc_chunks_v2` song song, `match_doc_chunks_v2` có tham số bật/tắt để đo A/B):
  [p2_doc_chunks_schema_review.md](../../reports/p2_doc_chunks_schema_review.md). Chờ Toma duyệt → D-009.
- Không đổi SQL trên Supabase, không đổi code retrieval.

- Quyết định (duyệt: Toma, từ I-43 của doc-ingest): tra cứu tài liệu (vector + FTS) chỉ khớp chunk con và độc
  lập; chunk cha chỉ để `Retriever._expand_parents` mở rộng ngữ cảnh. Chi tiết: [decisions.md](../../decisions.md)
  D-008, contract C2 S-03.
- Lý do: hiện `match_doc_chunks` tìm trên mọi chunk; cha + con cùng khớp chiếm 2 trong 6 suất `final_chunk_top_k`
  dù LLM chỉ nhận nội dung cha một lần.
- Chưa đổi code/SQL: cần cột `chunk_role` trong `doc_chunks` và điều kiện lọc trong `match_doc_chunks`; làm cùng
  loader mới khi xuất bản chunk builder (E-01: loader hiện ghi `parent_id = null`). Đo xác nhận ở Bước 4 của
  doc-ingest (biến thể "không tìm cha").
- Ảnh hưởng contract/API/schema: sẽ đổi schema `doc_chunks` (SQL idempotent, áp tay trước deploy).

## 2026-11-11 · Tách tài liệu luồng website-qa (D-002) · loại: thay đổi

- Vấn đề: thiết kế nằm trong `architecture.md` (143 dòng), trạng thái và lịch sử rải trong
  `current-state.md` (P5, rủi ro 4a và 9, việc 12c, Validation record, Context/RAG pipeline).
- Quyết định/luật: tách thành README, STATE, LOG; phần cũ chép nguyên văn vào archive (duyệt:
  Toma, D-002).
- File: `docs/ai/flows/website-qa/*`; `architecture.md`, `current-state.md` rút gọn;
  `api_guidelines.md` bỏ mục trạng thái (chuyển vào STATE).
- Kiểm chứng: từ `backend/`, `.\venv\Scripts\python.exe -m pytest tests` → 938 passed,
  14 skipped; `widget-backend` `npm test` → 22 pass.
- Ảnh hưởng contract/API/schema: không. Không đổi code.
