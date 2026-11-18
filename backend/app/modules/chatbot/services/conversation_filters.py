"""Bộ lọc, từ khoá và cursor của danh sách hội thoại Workspace (B2, FRONTEND_REQUIREMENTS 19.4–19.7).

Hàm thuần: router chuyển tham số query vào đây; lỗi tham số là `ConversationQueryError`
(router trả 422 với `code`). Repository nhận `ConversationFilters` đã chuẩn hoá.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from uuid import UUID

# Q19: ngày lọc tính theo giờ Việt Nam (UTC+7, không có giờ mùa hè).
VN_TZ = timezone(timedelta(hours=7))
MAX_RANGE_DAYS = 366
MIN_TOKEN_LENGTH = 2
MAX_TOKENS = 8
LIKE_ESCAPE = "\\"


class ConversationQueryError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def fold(text: str) -> str:
    """Chữ thường, bỏ dấu (kể cả đ → d): cùng kết quả với `public.immutable_unaccent(lower(x))`."""
    decomposed = unicodedata.normalize("NFD", text.lower().replace("đ", "d"))
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def like_escape(text: str) -> str:
    return text.replace(LIKE_ESCAPE, LIKE_ESCAPE * 2).replace("%", "\\%").replace("_", "\\_")


@dataclass(frozen=True)
class SearchTerms:
    """Từ khoá `q` (Q15, Q29): các nhánh khớp ghép bằng OR."""

    raw: str
    # Từ đã bỏ dấu, ≥ 2 ký tự: mọi từ phải có trong cùng một câu hỏi.
    tokens: tuple[str, ...]
    # Khớp chính xác mã hội thoại hoặc mã lượt.
    uuid: UUID | None
    # Mã ticket không có dấu # đầu; model sản phẩm so nguyên chuỗi (không phân biệt hoa thường).
    exact: str

    @classmethod
    def parse(cls, q: str) -> SearchTerms | None:
        raw = " ".join(q.split())
        if not raw:
            return None
        try:
            uuid = UUID(raw)
        except ValueError:
            uuid = None
        tokens = tuple(dict.fromkeys(
            token for token in (fold(part) for part in raw.split()) if len(token) >= MIN_TOKEN_LENGTH
        ))[:MAX_TOKENS]
        return cls(raw=raw, tokens=tokens, uuid=uuid, exact=raw.lstrip("#").strip())


@dataclass(frozen=True)
class ConversationFilters:
    terms: SearchTerms | None = None
    # completed | handoff | blocked | error | cancelled
    status: str | None = None
    channel: str | None = None
    product_models: tuple[str, ...] = ()
    # Khoảng UTC [start, end) từ from/to theo giờ Việt Nam.
    start: datetime | None = None
    end: datetime | None = None
    from_date: date | None = field(default=None, compare=False)
    to_date: date | None = field(default=None, compare=False)

    @property
    def has_range(self) -> bool:
        return self.start is not None

    def fingerprint(self) -> str:
        """Dấu của bộ lọc, gắn vào cursor để phát hiện cursor của bộ lọc khác."""
        payload = json.dumps([
            self.terms.raw if self.terms else None,
            self.status,
            self.channel,
            sorted(self.product_models),
            self.start.isoformat() if self.start else None,
            self.end.isoformat() if self.end else None,
        ])
        return hashlib.sha256(payload.encode()).hexdigest()[:16]


def date_range(from_date: date | None, to_date: date | None, *, today: date | None = None) -> tuple[datetime, datetime] | None:
    """Q19: cả hai đầu tính theo giờ Việt Nam → UTC `[from 00:00, to+1 00:00)`."""
    if from_date is None and to_date is None:
        return None
    today = today or datetime.now(VN_TZ).date()
    if from_date is None or to_date is None:
        raise ConversationQueryError("invalid_date_range", "Both from and to are required.")
    if from_date > to_date:
        raise ConversationQueryError("invalid_date_range", "from must not be after to.")
    if to_date > today:
        raise ConversationQueryError("invalid_date_range", "to must not be in the future.")
    if (to_date - from_date).days + 1 > MAX_RANGE_DAYS:
        raise ConversationQueryError("invalid_date_range", f"The range must not exceed {MAX_RANGE_DAYS} days.")
    start = datetime.combine(from_date, time.min, VN_TZ).astimezone(timezone.utc)
    end = datetime.combine(to_date + timedelta(days=1), time.min, VN_TZ).astimezone(timezone.utc)
    return start, end


def build_filters(
    *,
    q: str | None = None,
    status: str | None = None,
    channel: str | None = None,
    product_models: list[str] | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
    today: date | None = None,
) -> ConversationFilters:
    window = date_range(from_date, to_date, today=today)
    models = tuple(dict.fromkeys(model.strip() for model in product_models or [] if model.strip()))
    return ConversationFilters(
        terms=SearchTerms.parse(q) if q else None,
        status=status,
        channel=channel,
        product_models=models,
        start=window[0] if window else None,
        end=window[1] if window else None,
        from_date=from_date,
        to_date=to_date,
    )


def _b64(payload: dict) -> str:
    return base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode().rstrip("=")


def _unb64(cursor: str) -> dict:
    try:
        data = json.loads(base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)))
    except (ValueError, binascii.Error, UnicodeDecodeError) as exc:
        raise ConversationQueryError("invalid_cursor", "The cursor is not valid.") from exc
    if not isinstance(data, dict):
        raise ConversationQueryError("invalid_cursor", "The cursor is not valid.")
    return data


def _key(data: dict) -> tuple[datetime, UUID]:
    try:
        moment = datetime.fromisoformat(data["t"])
        ident = UUID(data["i"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ConversationQueryError("invalid_cursor", "The cursor is not valid.") from exc
    if moment.tzinfo is None:
        raise ConversationQueryError("invalid_cursor", "The cursor is not valid.")
    return moment, ident


def encode_cursor(moment: datetime, ident: UUID, filters: ConversationFilters | None = None) -> str:
    payload = {"t": moment.isoformat(), "i": str(ident)}
    if filters is not None:
        payload["f"] = filters.fingerprint()
    return _b64(payload)


def decode_cursor(cursor: str, filters: ConversationFilters | None = None) -> tuple[datetime, UUID]:
    """Khoá keyset `(thời điểm, id)` của dòng cuối trang trước; sai hoặc khác bộ lọc → `invalid_cursor`."""
    data = _unb64(cursor)
    if filters is not None and data.get("f") != filters.fingerprint():
        raise ConversationQueryError("invalid_cursor", "The cursor does not match the current filters.")
    return _key(data)
