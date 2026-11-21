"""Đối tượng xem tài liệu theo kênh (2026-11-21): chốt chặn dữ liệu cho `doc_chunks_v2.audience`.

Website chỉ thấy chunk `public`; kênh CRM thấy cả `internal`. Kênh lạ hoặc thiếu thì lấy tập hẹp nhất
(`public`) để lỗi cấu hình không làm lộ tài liệu nội bộ.
"""

from app.modules.chatbot.schemas.default import ChannelType

PUBLIC = "public"
INTERNAL = "internal"
AUDIENCES: tuple[str, ...] = (PUBLIC, INTERNAL)
DEFAULT_AUDIENCES: tuple[str, ...] = (PUBLIC,)

_BY_CHANNEL: dict[ChannelType, tuple[str, ...]] = {
    ChannelType.WEBSITE: (PUBLIC,),
    ChannelType.CRM: (PUBLIC, INTERNAL),
}


def audiences_for(channel: ChannelType | str | None) -> tuple[str, ...]:
    try:
        return _BY_CHANNEL[ChannelType(channel)]
    except (KeyError, ValueError):
        return DEFAULT_AUDIENCES
