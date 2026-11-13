# Luồng <tên> (`<module>`)

Thiết kế của luồng. Sửa khi thiết kế đổi; trạng thái ghi ở [STATE.md](STATE.md), lịch sử
ghi ở [LOG.md](LOG.md). Giới hạn: 200 dòng.

## Phạm vi

<Luồng làm gì, không làm gì. Một đoạn.>

## Điểm vào

| Loại | Vị trí | Ghi chú |
|---|---|---|
| route / CLI / script | `đường/dẫn.py` | |

## Pipeline

```text
<sơ đồ các bước theo thứ tự, kèm file đầu ra nếu có>
```

| Vùng | File | Vai trò |
|---|---|---|

## Contract

<Schema chính, SSE event, mã lỗi. Trỏ tới tài liệu contract thay vì chép lại.>

## Bất biến của luồng

<Quy tắc chỉ đúng cho luồng này. Quy tắc đúng cho từ hai luồng trở lên nằm ở
[team-rules.md](../../rules/team-rules.md).>

## Cấu hình

| Biến hoặc file | Mặc định | Tác dụng |
|---|---|---|

## Test và eval

```powershell
<lệnh, ghi rõ thư mục chạy và venv>
```

## Log runtime

<Dữ liệu chạy thật nằm ở đâu: bảng, thư mục, dòng log. Đây không phải LOG.md.>

## Ranh giới với luồng khác

<Module dùng chung, thứ không được import, dữ liệu trao đổi.>

## Tài liệu sâu hơn

<Liên kết tới contract, báo cáo, spec.>
