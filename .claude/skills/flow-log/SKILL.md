---
name: flow-log
description: "Ghi nhật ký và trạng thái của luồng QS Technology sau mỗi thay đổi: thêm mục vào đầu docs/ai/flows/<luồng>/LOG.md, viết lại STATE.md, lan truyền sang current-state.md, decisions.md, README và luồng phụ thuộc, rồi chạy check_ai_docs. Dùng skill này mỗi khi vừa sửa code, cấu hình, SQL hay tài liệu thiết kế của một luồng (crm-agent, website-qa, chat-platform, doc-ingest, learning, workspace-ui); khi chốt một quyết định hay đổi contract; khi kiểm chứng hoặc đo trên dữ liệu thật; khi gặp sự cố (lỗi provider, hết credit, deploy chưa lên); khi bàn giao phiên; hoặc khi người dùng nói \"ghi log\", \"cập nhật STATE\", \"ghi nhận thay đổi\", \"báo cáo trạng thái luồng\", kể cả khi họ không nhắc tên file."
---

# Ghi nhật ký và trạng thái luồng

Mỗi luồng trong `docs/ai/flows/<luồng>/` có ba file: `README.md` (thiết kế), `STATE.md` (ảnh chụp
hiện tại) và `LOG.md` (nhật ký, mới nhất ở trên). Agent kế tiếp, dù là Claude, Copilot hay người,
bắt đầu bằng cách đọc STATE rồi tra LOG khi cần biết *vì sao*. Hai file này sai hoặc thiếu thì
agent kế tiếp sẽ dựng tiếp trên thứ không tồn tại, hoặc làm lại một quyết định đã chốt. Vì vậy
mục tiêu của skill là: **người đọc sau chỉ cần STATE để biết đang ở đâu, và LOG để biết đã quyết
gì, dựa trên bằng chứng nào.**

Nguồn quy ước: `AGENTS.md` (Quy trình bước 5), `docs/ai/rules/team-rules.md` (TR-10, TR-11, TR-12,
TR-14, TR-17), mẫu `docs/ai/flows/_template/LOG.md` và `_template/STATE.md`. Skill này không thay
các nguồn đó; nếu chúng đổi thì theo chúng.

## Quy trình

### 1. Xác định luồng và loại mục

- Dùng bảng **Chỉ mục luồng** trong `AGENTS.md` để ánh xạ file đã đổi sang luồng. Thay đổi chạm
  nhiều luồng: luồng sở hữu code thay đổi nhận mục đầy đủ; mỗi luồng bị ảnh hưởng nhận một mục
  ngắn (2–4 dòng) nói ảnh hưởng với nó và trỏ sang mục đầy đủ. Ví dụ: đổi retriever của website-qa
  thì crm-agent (tool `product_docs_ask` dùng lại `RetrievalPipeline`) cũng cần mục ngắn.
- Chọn **loại** trong danh sách sau, có thể ghép hai loại bằng dấu phẩy. Dùng đúng các từ này để
  người đọc lọc được LOG:

  | Loại | Khi nào |
  |---|---|
  | `thay đổi` | Sửa code, cấu hình, SQL, prompt, tài liệu thiết kế |
  | `quyết định` | Chốt hướng, luật, contract, tham số (kèm người duyệt) |
  | `kiểm chứng` | Kiểm trên dữ liệu, server hoặc tài khoản thật; smoke test |
  | `đánh giá` | Đo, eval, phân tích nguyên nhân, so sánh phương án |
  | `sự cố` | Lỗi vận hành, provider, dữ liệu, deploy; việc bị chặn |
  | `triển khai` | Áp SQL, nạp dữ liệu, merge, deploy lên môi trường |
  | `tài liệu` | Chỉ sửa tài liệu hoặc bàn giao phiên, không đổi hành vi |

### 2. Thu thập bằng chứng trước khi viết

Viết LOG từ bằng chứng, không từ trí nhớ về điều mình *định* làm (TR-14).

- **Phạm vi thật:** `git status --short` và `git diff --stat` (hoặc diff với nhánh gốc) để liệt kê
  file. Đừng ghi file chỉ định sửa mà chưa sửa.
- **Validation:** lệnh đã chạy và kết quả nguyên văn (số passed/failed/skipped). Có lỗi thì tách
  **lỗi có sẵn** khỏi **lỗi do thay đổi**, kèm lý do. Ví dụ: hash CSV khác vì worktree checkout bằng
  CRLF, blob trong git vẫn đúng. Lệnh nào không chạy được hoặc không chạy thì ghi rõ và nói vì sao.
- **Trạng thái phát hành:** đã commit chưa, nhánh nào, đã merge hay push chưa, server hoặc môi trường
  đang chạy bản nào. "Đã merge" không có nghĩa là server đang chạy code mới, nên chỉ ghi "đã chạy
  trên môi trường X" khi đã kiểm (trace, log khởi động, commit của checkout đang chạy).
- **Kiểm trên dữ liệu thật:** nêu trace, run id hoặc thư mục kết quả để người sau tra lại. Không ghi
  nội dung tin nhắn, token hay secret vào LOG (rule chat-platform).

### 3. Thêm mục vào đầu LOG.md

Chèn ngay sau phần mở đầu của file (trên mục mới nhất hiện có). Không sửa mục cũ. Nếu mục cũ sai,
thêm mục mới đính chính và trỏ về mục cũ theo ngày và tiêu đề.

```
## YYYY-MM-DD · <tiêu đề nói kết quả, không nói hoạt động> (<ID>) · loại: <loại>

- Vấn đề: <điều gì sai hoặc thiếu, ở đâu, vì sao cần làm>
- Quyết định/luật: <nội dung> (duyệt: <ai, ngày>; căn cứ: <số đo, báo cáo, mục LOG>)
- File: <file đã sửa; test đã thêm hoặc sửa>
- Kiểm chứng: <lệnh> → <kết quả>; <trace/run id nếu có>
- Ảnh hưởng contract/API/schema/cấu hình: <có: gì, cờ mới, mặc định | không>
- Chưa kiểm / mở tiếp: <việc còn lại, ID vấn đề, ai chờ ai>
```

Bỏ dòng không áp dụng, nhưng **giữ "Kiểm chứng" và "Chưa kiểm / mở tiếp"** cho mọi mục `thay đổi`,
`kiểm chứng`, `triển khai`: đó là hai dòng người đọc sau cần nhất để biết tin được tới đâu.

Cách viết để agent khác hiểu đúng:
- **Tiêu đề nói kết quả:** "Chat chuyển sang doc_chunks_v2", không phải "Làm việc với retriever".
- **Dùng ID sẵn có** của luồng (I-xx, R-x, D-xxx, B-x, BL-xx, T-xx). Ý mới chưa có ID mà cần theo
  dõi thì đặt ID theo tiền tố của luồng và đưa vào bảng "Vấn đề mở" của STATE.
- **Quyết định ghi đủ ba phần:** chọn gì, ai duyệt, căn cứ (con số hoặc báo cáo). Phương án bị loại
  và lý do chỉ cần một dòng để tránh người sau đề xuất lại. Agent không tự duyệt quyết định thay
  người dùng; chưa có người duyệt thì ghi "chờ <ai> duyệt" và để loại là `đánh giá`.
- **Phân biệt mức chín** (TR-10): "code + test bằng fake", "đã kiểm trên Supabase thật", "chỉ eval
  dùng", "scaffold". Không viết "đã xong" khi mới qua unit test.
- **Ngày tuyệt đối** (YYYY-MM-DD), không viết "hôm qua" hay "tuần sau".
- Chi tiết dài (bảng số đo, danh sách câu) đặt trong `docs/ai/reports/` rồi trỏ tới, giữ mục LOG
  ngắn. Một mục thường dài 5–15 dòng.

Ví dụ tốt và lỗi hay gặp: đọc [references/examples.md](references/examples.md) khi viết mục
`quyết định`, `sự cố`, hoặc khi chưa chắc cách viết.

### 4. Viết lại STATE.md

STATE là ảnh chụp, không phải nhật ký: **viết lại** các phần bị ảnh hưởng, không nối thêm dòng
"cập nhật ngày…" (TR-17).

- Sửa dòng `Cập nhật: YYYY-MM-DD`.
- **Tóm tắt** (3–6 gạch): đúng với hiện tại sau thay đổi. Xoá câu đã lỗi thời. Ví dụ: "chat vẫn dùng
  bảng cũ" phải biến mất khi đã chuyển bảng.
- **Độ chín từng phần:** cập nhật trạng thái (có / một phần / chưa có / scaffold / chỉ eval) và ghi chú.
- **Vấn đề mở:** vấn đề đã đóng thì bỏ khỏi bảng (lịch sử nằm ở LOG). Vấn đề mới thì thêm kèm ID.
  Cảnh báo vận hành quan trọng (cờ mặc định làm tính năng không chạy, secret hết hạn) đặt ở Tóm tắt.
- **Kết quả kiểm gần nhất:** thay bằng lần kiểm mới, kèm môi trường. Giữ tối đa một lần cũ nếu còn
  cần để so sánh.
- **Bước tiếp theo:** đánh lại số, bỏ bước đã làm, nêu ai làm (Toma, agent).
- Giữ **≤ 80 dòng** (check_ai_docs kiểm). Dài quá thì gom chi tiết sang LOG hoặc báo cáo.
- Nếu thấy STATE đang lệch với code, kiểm code rồi sửa STATE trong cùng lần (TR-11) và ghi trong
  mục LOG là đã đính chính gì.

### 5. Lan truyền sang tài liệu khác

Một thông tin chỉ có một nơi ở, nhưng mỗi nơi tham chiếu nó phải còn đúng. Đi qua danh sách này:

| Nếu thay đổi… | Thì cập nhật |
|---|---|
| Đổi trạng thái tổng của luồng (câu trong cột "Trạng thái" không còn đúng) | Dòng của luồng trong `docs/ai/current-state.md` |
| Có quyết định liên luồng, hoặc làm xong một bước của quyết định D-xxx | `docs/ai/decisions.md` (thêm dòng hoặc sửa cột trạng thái) |
| Đổi thiết kế: file, pipeline, bảng cấu hình, ranh giới với luồng khác | `README.md` của luồng |
| Đổi route, schema HTTP, SSE event, mã lỗi | `docs/ai/api_guidelines.md` (TR-06) |
| Thêm hoặc đổi cờ, biến môi trường, SQL cần áp tay | Bảng cấu hình trong README; `docs/ai/rules/deploy-rules.md` nếu có quy tắc deploy |
| Ảnh hưởng luồng khác | Mục LOG ngắn và dòng STATE của luồng đó |

Hay bị quên nhất là dòng trong `current-state.md` và mục ngắn ở luồng phụ thuộc. Hãy grep câu
trạng thái cũ (ví dụ tên bảng, tên cờ) trong `docs/ai/` để tìm chỗ còn nói điều đã hết đúng.
Không sửa `docs/ai/archive/` và các file `LOG-archive-*.md`: đó là lịch sử.

### 6. Kiểm và giữ kích thước

Từ thư mục `backend`:

```powershell
$env:PYTHONIOENCODING = "utf-8"; .\venv\Scripts\python.exe scripts\check_ai_docs.py
```

(`PYTHONIOENCODING` tránh lỗi in tiếng Việt trên console Windows.) Script kiểm: đủ ba file, STATE
≤ 80 dòng và có dòng `Cập nhật:`, mục LOG mới nhất ở trên, link không gãy. Không đạt thì sửa rồi
chạy lại.

Nếu `LOG.md` vượt 300 dòng, đề xuất với người dùng việc cắt các mục cũ sang
`LOG-archive-<ngày của mục mới nhất bị cắt>.md` và để link ở đầu file. Không tự cắt nếu người dùng
chưa đồng ý, vì đây là thao tác lớn trên lịch sử.

### 7. Báo lại cho người dùng

Kết thúc bằng tóm tắt ngắn theo mục "Báo cáo khi xong" của `AGENTS.md`: thay đổi gì, file nào, lệnh
validation và kết quả, vấn đề còn mở, ảnh hưởng contract. Đồng thời nêu các file tài liệu đã cập
nhật (LOG, STATE, current-state, decisions…). Nếu tài liệu đang có thay đổi chưa commit của người
khác trong cùng file, nói rõ để họ biết có thể phải gộp khi merge.

## Khi không cần ghi

- Câu hỏi hoặc điều tra chỉ đọc, không đổi gì và không rút ra kết luận mới: không ghi LOG.
- Điều tra có kết luận mới đáng giữ (nguyên nhân sự cố, số đo, kiểm chứng trên môi trường thật)
  thì ghi một mục `kiểm chứng`, `đánh giá` hoặc `sự cố`, dù không sửa code.
- Thay đổi nhỏ trong cùng một việc đang làm: gộp vào một mục cho cả việc khi xong, không ghi mỗi
  lần sửa một mục.
