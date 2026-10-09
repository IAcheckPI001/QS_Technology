# SecurityStage pipeline

## 1. Mục đích và phạm vi

`SecurityStage` là một stage độc lập trong chatbot pipeline, chịu trách nhiệm
kiểm tra an toàn request trước khi request đi vào context, retrieval hoặc LLM
provider.

Mục tiêu của phiên bản đầu tiên:

- phát hiện các dấu hiệu prompt injection phổ biến;
- phát hiện các nội dung thuộc policy bị chặn;
- giữ nguyên nội dung gốc để lưu trữ và hiển thị khi request được cho phép;
- cung cấp một quyết định typed để pipeline có thể tiếp tục hoặc dừng;
- không để router hoặc provider biết chi tiết implementation của detector;
- không ghi raw request vào log.

Phạm vi ban đầu không bao gồm:

- moderation bằng một LLM khác;
- tự động rewrite hoặc làm sạch nội dung người dùng trước khi gửi provider;
- xây dựng hệ thống history/audit riêng;
- thay thế validation của Pydantic;
- giải quyết authorization tổng quát cho toàn bộ hệ thống.

## 2. Trạng thái hiện tại

Kiến trúc tổng quát được mô tả trong
[architecture.md](./architecture.md). Chat flow đang hoạt động thực tế là:

```text
Client
  -> API router / SSE transport
  -> ChatbotService
  -> OpenAI provider
  -> HistoryRepository
  -> Supabase public.chat_history
```

Các thành phần liên quan hiện có:

| Thành phần | Trạng thái hiện tại | Tác động |
|---|---|---|
| `backend/app/modules/chatbot/stages/default.py` | Có protocol/pipeline scaffold, chưa có executor thực tế | Cần chuẩn hóa contract và điểm chạy stage |
| `backend/app/modules/chatbot/schemas/system/run_state.py` | Có `RunState` cho pipeline tương lai | Có thể thêm security result typed |
| `backend/app/util/normalize.py` | Có NFC, casefold và accent-fold views | Cần bỏ `print` raw text và mở rộng test |
| `backend/app/modules/chatbot/service.py` | Gọi provider trực tiếp và ghi history | Cần gọi security pipeline trước provider |
| `backend/app/modules/chatbot/router.py` | Xử lý dependency và SSE transport | Không đặt detector vào router |
| `backend/app/modules/chatbot/schemas/default.py` | `MessageText` tối đa 4.000 ký tự | Đã xử lý giới hạn ký tự cơ bản |
| `backend/tests/chatbot/test_normalize_input.py` | Có test normalize cơ bản | Cần bổ sung test bảo mật và regression |

`MessageText` hiện có `max_length=4000`. Vì vậy giới hạn ký tự request là
schema concern; `OverflowHandler` chỉ cần thêm nếu về sau có giới hạn token,
context hoặc payload sau khi ghép lịch sử.

## 3. Pipeline mục tiêu

Với quyết định hiện tại, thứ tự v1 là:

```text
1. Parse request và validate schema
2. Kiểm tra format các trường bắt buộc
3. Kiểm tra session tồn tại và quyền truy cập
4. SecurityStage
   4.1 Normalize
   4.2 InjectionGuard
   4.3 ContentPolicy
   4.4 Token/context overflow policy nếu được bật
5. Context / retrieval
6. Gọi LLM provider
7. Ghi history và trả response
```

### 3.1 Ranh giới validation và security

- **Schema validation** kiểm tra kiểu dữ liệu, trường bắt buộc, chuỗi rỗng và
  giới hạn 4.000 ký tự.
- **Session validation/authorization** kiểm tra identifier và quyền dùng
  session. Không được coi `session_id` client gửi lên là credential.
- **SecurityStage** kiểm tra nội dung request và policy.
- **Context/retrieval/provider** chỉ chạy sau khi quyết định là `allow`.
- **Router** chỉ làm transport, dependency wiring và mapping lỗi.
- **Provider** không chứa rule injection hoặc blacklist.

Việc tra cứu session trước SecurityStage là quyết định v1 theo yêu cầu hiện tại.
Trade-off là database lookup xảy ra trước khi content filtering. Nếu chi phí hoặc
privacy risk trở thành vấn đề, có thể đưa các kiểm tra rẻ, không cần database
như null-byte và giới hạn cơ bản lên trước session lookup trong một thay đổi
policy riêng.

## 4. Contract của stage

### 4.1 Stage protocol

Pipeline cần có protocol rõ ràng thay cho scaffold chưa hoàn chỉnh:

```text
Stage.execute(state) -> StageResult
```

`StageResult` phải là kiểu nội bộ rõ ràng, tối thiểu có:

- `action`: `CONTINUE`, `BLOCK` hoặc `REVIEW`;
- `stage_name`;
- findings đã chuẩn hóa;
- severity cao nhất;
- policy version;
- latency/metadata không chứa raw input.

`SecurityStage` không tự trả HTTP response và không tự stream SSE. Nó chỉ cập
nhật state và trả decision cho orchestrator.

### 4.2 Security decision v1

Mặc định v1:

| Action | Ý nghĩa | Hành vi pipeline |
|---|---|---|
| `allow` | Không có finding chặn | Tiếp tục context/provider |
| `block` | Có rule bảo mật hoặc policy cấm | Dừng trước context/provider |
| `review` | Chưa dùng trong flow synchronous v1 | Dành cho future human review hoặc queue |

V1 chỉ sử dụng `allow` và `block` trong request flow. `review` có thể tồn tại
trong contract để tránh breaking change khi bổ sung asynchronous review.

Finding nên có:

- `detector_id`;
- `category`;
- `severity`;
- `rule_id`;
- `confidence` nếu detector có thể tính;
- evidence đã redacted hoặc chỉ metadata vị trí, không chứa toàn bộ input.

### 4.3 Precedence

Khi nhiều detector match:

1. `block` thắng `allow`;
2. severity cao nhất được dùng làm severity tổng hợp;
3. các `rule_id` được sắp xếp ổn định để log/metric có thể đối chiếu;
4. không trả chi tiết rule nội bộ cho client.

Lỗi load policy hoặc lỗi cấu hình detector là lỗi hệ thống, không phải
`allow`. V1 nên fail-closed đối với policy bắt buộc để tránh vô tình bypass
security stage; lỗi phải được log bằng request ID và trả error code tổng quát.

## 5. Các thành phần cần triển khai

### 5.1 Normalize

Giữ helper hiện tại trong
[backend/app/util/normalize.py](../backend/app/util/normalize.py) hoặc chuyển
vào security domain nếu cần thống nhất ownership.

Yêu cầu:

- giữ `original_text`, không sửa text gửi provider;
- tạo NFC view;
- tạo casefold view;
- tạo accent-folded view cho tiếng Việt;
- cân nhắc detection view loại zero-width/control characters mà không làm mất
  original text;
- không `print` hoặc log raw text;
- dùng helper thuần, deterministic, không phụ thuộc provider.

Normalize chạy một lần cho mỗi request và truyền kết quả cho các detector để
tránh mỗi detector tự normalize lại.

### 5.2 InjectionGuard

`InjectionGuard` là detector thuần, không quyết định HTTP status. Rule catalog v1
phải có ID, category, severity và pattern.

Các nhóm rule ban đầu:

| Category | Ví dụ | Mặc định |
|---|---|---|
| `ignore_instructions` | `ignore previous/prior/above instructions` | block khi match rõ |
| `role_override` | `you are now`, `pretend you are`, `act as if` | block khi dùng như instruction |
| `system_tags` | `<system>`, `[SYSTEM]`, `[INST]`, `<<SYS>>` | block |
| `instruction_injection` | `new instruction:`, `override:`, `system prompt:` | block khi có ngữ cảnh chỉ thị |
| `null_bytes` | `\x00` | block |
| `delimiter_escape` | `end of system`, `begin user input`, pseudo-tags | block khi match rõ |

Không dùng một substring blacklist đơn giản cho mọi trường hợp. Rule phải:

- chạy trên các normalized views phù hợp;
- có boundary hoặc context requirement;
- tránh match một câu hỏi mô tả khái niệm một cách máy móc nếu policy cho
  phép;
- được kiểm thử cả positive và negative cases;
- có giới hạn số rule và thời gian đánh giá để tránh regex DoS.

V1 không rewrite request và không loại bỏ đoạn match.

### 5.3 ContentPolicy

`ContentPolicy` tách biệt khỏi injection detection. Nó nhận normalized input và
policy configuration versioned.

V1 cần chốt danh mục cụ thể thay vì dùng nhãn rộng như “chính trị” để block mọi
request. Mỗi policy entry nên có:

- `policy_id`;
- category/topic;
- pattern hoặc classifier strategy;
- ngôn ngữ áp dụng;
- action;
- severity;
- policy version;
- lý do nghiệp vụ.

Mặc định v1 chỉ block các category đã được phê duyệt rõ trong policy catalog.
Các match mơ hồ không được silently block nếu chưa có yêu cầu nghiệp vụ; chúng
phải được metric hoặc đưa vào chế độ review ở giai đoạn sau.

### 5.4 OverflowHandler

Không triển khai như một detector độc lập trong v1 nếu chỉ kiểm tra số ký tự,
vì schema đã giới hạn `MessageText` ở 4.000 ký tự.

Chỉ thêm thành phần này khi có yêu cầu:

- giới hạn token sau tokenize;
- giới hạn tổng prompt sau ghép context;
- giới hạn lịch sử hội thoại;
- giới hạn chi phí provider.

Hành vi mặc định phải là `block` với error code rõ ràng. Không truncate âm thầm
vì sẽ thay đổi ý nghĩa request và có thể làm mất phần injection hoặc điều kiện
quan trọng.

## 6. Tích hợp vào service và session flow

`ChatbotService` hoặc một orchestrator riêng phải thực hiện:

1. nhận inbound model đã validate;
2. resolve và authorize session;
3. tạo `RunState`;
4. chạy `SecurityStage`;
5. nếu `block`, dừng trước khi tạo provider messages/context;
6. nếu `allow`, tiếp tục flow hiện tại;
7. chỉ ghi `completed` sau khi provider stream thành công.

Router trong [backend/app/modules/chatbot/router.py](../backend/app/modules/chatbot/router.py)
chỉ nên map decision/error thành transport response. Không đưa rule matching vào
route handler.

### 6.1 Block behavior

Blocked request phải:

- không gọi provider;
- không chạy retrieval/context tốn tài nguyên;
- không phát provider SSE `delta`;
- trả SSE `error` với code ổn định `request_blocked`;
- trả thông báo từ backend response catalog theo locale đã allowlist;
- không trả rule/pattern/evidence;
- có `X-Request-ID` để support tra cứu telemetry;
- tạo một `ChatHistory` với `status='blocked'`, `model=None` và response catalog
  trong `answer`;

`request_blocked` là security-policy outcome, không phải provider/network
failure. Backend ghi event với `status=blocked`, policy version,
detector/category/severity và latency, nhưng không ghi raw message. Frontend
phân biệt code này với lỗi kỹ thuật, render message như assistant, không retry
và không hiển thị nó ở khu vực lỗi chung.

Blocked record được lưu trong `ChatHistory` hiện có để history UI có thể hiển thị
đầy đủ. History/context query phải phân tách: UI có thể đọc `blocked`, còn
context builder chỉ được đọc `status='completed'`. V1 không cần migration mới,
nhưng raw `query_origin` phải tuân theo retention và access control của history.

### 6.2 Error mapping

Các nhóm lỗi phải phân biệt:

| Nhóm | Ví dụ | Transport |
|---|---|---|
| Validation | schema, empty text, length | HTTP validation response |
| Session | database unavailable, unauthorized session | response tổng quát, không leak existence |
| Security block | injection/content policy | `request_blocked` |
| Security system failure | policy load/config failure | service unavailable hoặc internal error |
| Provider | upstream LLM failure | provider error hiện có |

Không dùng exception broad catch để biến security system failure thành `allow`.

## 7. Observability và privacy

Được phép ghi:

- request ID;
- session ID đã được kiểm soát quyền;
- stage name;
- detector ID/category/severity;
- policy version;
- latency;
- decision;
- số lượng findings.

Không ghi:

- raw message;
- toàn bộ normalized views;
- system prompt;
- nội dung evidence chưa redacted;
- secret hoặc credential.

Metrics v1 nên có:

- số request `allow`/`block`;
- block theo detector/category;
- security stage latency;
- policy/configuration failure count;
- số request bị chặn trước provider.

Các metrics cần tránh dùng label có cardinality cao như raw text, message ID của
người dùng hoặc nội dung rule động.

## 8. Tác động

### API và SSE

- SSE `error` giữ nguyên transport hiện tại và dùng `code=request_blocked` cùng
  message từ backend response catalog.
- Backend response catalog hỗ trợ locale allowlist `vi`/`en`; locale client chỉ
  dùng cho hiển thị sau normalize/fallback, không phải trusted input.
- Success response và SSE `delta`/`done` giữ nguyên.
- Client không cần biết implementation của detector.
- Error payload phải ổn định nhưng không tiết lộ policy nội bộ.

### Schema và state

- Thêm internal security result vào `RunState` hoặc execution context.
- Không cần thay đổi inbound contract nếu không bổ sung field policy.
- Nếu expose status ra API, cần schema versioning.

### Database

- V1 tái sử dụng các field hiện có để lưu `status='blocked'`, không cần migration.
- History UI được phép hiển thị blocked record sau authorization.
- Context query bắt buộc lọc `status='completed'`; blocked không được đưa vào LLM.
- Nếu sau này cần aggregate detector/policy typed, thêm migration hoặc bảng audit
  riêng.

### Dependencies

- Ưu tiên Python standard library và dependency hiện có.
- Không thêm framework moderation hoặc provider mới trong v1.
- Regex phải được giới hạn và review để tránh biểu thức gây quá tải.

### Performance

- Normalize một lần.
- Detector phải bounded về số rule và độ phức tạp.
- Đo latency riêng của SecurityStage.
- Chặn sớm giúp tránh chi phí context/retrieval/provider.

### Backward compatibility

- Request hợp lệ tiếp tục đi qua flow hiện tại.
- Việc mở rộng block policy có thể làm thay đổi behavior của request trước đây
  được allow; phải version policy và rollout có kiểm soát.
- Không thay đổi semantics session ID trong cùng thay đổi nếu không có quyết định
  authorization riêng.

## 9. Ma trận file ảnh hưởng

| File/module | Loại thay đổi dự kiến | Mục đích |
|---|---|---|
| `docs/ai/security-stage-pipeline.md` | Tài liệu | Contract, pipeline, impacts, rollout |
| `docs/ai/architecture.md` | Có thể cập nhật | Ghi SecurityStage vào kiến trúc nếu đã triển khai |
| `docs/ai/current-state.md` | Có thể cập nhật | Trạng thái thực tế và known risks |
| `docs/ai/decisions.md` | Có thể cập nhật | Quyết định policy/authorization/retention |
| `backend/app/modules/chatbot/stages/default.py` | Sửa scaffold | Stage protocol, result và executor |
| `backend/app/modules/chatbot/stages/security/` | Mới | Normalize adapter, InjectionGuard, ContentPolicy, SecurityStage |
| `backend/app/modules/chatbot/stages/security/policies/` | Mới | Versioned injection rule và response catalog |
| `backend/app/modules/chatbot/schemas/system/run_state.py` | Sửa | Lưu security result typed |
| `backend/app/modules/chatbot/schemas/system/` | Mới/sửa | Security finding/decision schema |
| `backend/app/modules/chatbot/schemas/default.py` | Có thể sửa | Shared constants hoặc token policy |
| `backend/app/util/normalize.py` | Sửa | Bỏ raw-text print, bổ sung detection views nếu cần |
| `backend/app/modules/chatbot/service.py` | Sửa | Chạy stage trước provider |
| `backend/app/modules/chatbot/router.py` | Có thể sửa nhỏ | Mapping security error/SSE nếu cần |
| `backend/app/api/v1/dependencies.py` | Có thể sửa | Dependency injection cho policy/stage |
| `backend/app/core/config.py` | Có thể sửa | Policy settings không chứa secret |
| `backend/tests/chatbot/test_normalize_input.py` | Sửa | Regression normalize |
| `backend/tests/chatbot/test_security_stage.py` | Mới | Unit detector và aggregation |
| `backend/tests/chatbot/test_security_responses.py` | Mới | Locale allowlist và response catalog |
| `backend/tests/chatbot/test_chatbot_service.py` | Mới/sửa | Provider không được gọi khi block |
| `backend/tests/chatbot/test_chatbot_schema.py` | Có thể sửa | Contract/state validation |

Danh sách trên là phạm vi dự kiến; chỉ sửa các file thực sự cần thiết sau khi
contract v1 được chốt.

## 10. Chiến lược kiểm thử

### Unit tests

- NFC composition.
- Casefold và accent folding tiếng Việt.
- Zero-width/control character handling.
- Null byte.
- Mỗi InjectionGuard category.
- Positive/negative cases cho boundary và context.
- ContentPolicy category và policy version.
- Aggregate nhiều findings theo severity.
- Policy/configuration failure không trở thành `allow`.

### Integration tests

- Request hợp lệ đi tiếp tới provider.
- Request bị block không gọi provider.
- Request bị block không chạy context/retrieval.
- Request bị block không phát provider `delta`; SSE `error` chứa
  `request_blocked` và catalog message.
- Session invalid/unauthorized được xử lý trước SecurityStage theo flow v1.
- Provider failure vẫn giữ error behavior hiện tại.
- Không tạo history `completed` cho blocked request.

### Regression và validation

- Chạy focused backend pytest.
- Chạy formatter/linter backend theo command hiện có.
- Chạy import/startup validation.
- Chạy `npm run build` và `npm run lint` theo repository instruction; ghi rõ
  failure baseline không liên quan nếu có.

## 11. Rollout

### Giai đoạn 1 — Shadow mode

- Detector chạy nhưng chưa block provider.
- Chỉ ghi metric không chứa raw input.
- Đo false positive, latency và category distribution.

### Giai đoạn 2 — Block rule chắc chắn

- Bật block cho null byte, system tags rõ ràng và injection pattern có confidence
  cao.
- Giữ các policy mơ hồ ở monitor/review.

### Giai đoạn 3 — Content policy có version

- Bật từng category đã được nghiệp vụ phê duyệt.
- Có rollback bằng policy version/feature flag.
- Theo dõi tỷ lệ block và complaint trước khi mở rộng.

Mặc dù contract có `review`, synchronous chatbot flow v1 chưa cần hàng đợi
review. Nếu bật review trong tương lai, phải định nghĩa timeout, fallback và
response contract riêng.

## 12. Rủi ro và quyết định còn lại

1. **Session lookup trước security**: đúng yêu cầu v1 nhưng có thêm database
   exposure trước khi lọc content.
2. **`resolve_session_id` hiện tạo UUID mới cho session ID invalid/unknown**:
   cần quyết định lại nếu authorization nghiêm ngặt yêu cầu phân biệt invalid,
   unknown và missing session.
3. **Không có pipeline executor thực tế**: cần hoàn thiện seam trước khi tuyên
   bố SecurityStage đã được tích hợp.
4. **False positive của ContentPolicy**: không dùng blacklist rộng nếu chưa có
   taxonomy và test nghiệp vụ.
5. **Regex bypass/DoS**: cần test obfuscation, giới hạn pattern và review rule.
6. **Audit privacy**: không lưu raw blocked request nếu chưa có retention,
   ownership và access control.
7. **History error transaction**: khi tích hợp cần bảo đảm security/provider
   errors không làm sai semantics history đã mô tả trong
   [current-state.md](./current-state.md).

## 13. Tiêu chí hoàn thành triển khai

- Có stage protocol/executor và decision typed.
- SecurityStage chạy sau schema/session authorization, trước context/provider.
- Normalize không log raw text.
- InjectionGuard và ContentPolicy có rule/policy versioned.
- Blocked request không gọi provider và không ghi `completed`.
- Có unit/integration/regression tests cho các hành vi trên.
- Error mapping và observability không làm lộ nội dung người dùng.
- Tài liệu kiến trúc/current-state/decisions được cập nhật nếu implementation
  làm thay đổi quyết định đã ghi nhận.
