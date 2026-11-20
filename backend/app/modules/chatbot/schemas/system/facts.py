"""Trạng thái phiên có cấu trúc của luồng agent (Đợt 1 gói A, lớp L2).

Chỉ code ghi, từ output tool (không từ câu trả lời của LLM). Chỉ chứa định danh và nhãn ngắn:
id, mã, username, họ tên hoặc tiêu đề (≤ 80 ký tự). Không chứa số liệu, trạng thái, nội dung tin
nhắn, SĐT, email khách, địa chỉ, ghi chú: số liệu luôn phải tra lại. Lưu trong
`chat_history.conversation_state.facts` (ảnh chụp mỗi lượt).
"""

from typing import Literal

from pydantic import Field

from ..default import SystemModel

EntityKind = Literal["person", "customer", "model", "record"]

MAX_LABEL_CHARS = 80
MAX_ENTITIES = 20            # tổng thực thể giữ trong phiên
MAX_LOOKUPS = 5              # số lần tra gần nhất giữ lại
MAX_LIST_ROWS = 10           # mỗi danh sách chỉ ghi chừng này dòng đầu (có ordinal)
FACT_TTL_TURNS = 10          # mục không được nhắc lại sau chừng này lượt thì bị bỏ


def clip(text: str, limit: int = MAX_LABEL_CHARS) -> str:
    """Một dòng, cắt độ dài: nhãn là dữ liệu hiển thị, không mang xuống dòng hay chỉ dẫn dài."""
    flat = " ".join(str(text).split())
    return flat if len(flat) <= limit else flat[: limit - 1] + "…"


class SessionEntity(SystemModel):
    kind: EntityKind
    table: str | None = None               # bảng CRM nguồn; None với model sản phẩm
    id: str | None = None                  # UUID nguyên văn từ tool
    keys: dict[str, str] = Field(default_factory=dict)   # username, code
    label: str = ""
    ordinal: int | None = None             # vị trí trong danh sách gần nhất (1 = dòng đầu)
    source_tool: str
    turn: int = 0                          # lượt gần nhất thực thể được tool trả lại

    def same_as(self, other: "SessionEntity") -> bool:
        if self.table != other.table or self.kind != other.kind:
            return False
        if self.id and other.id:
            return self.id == other.id
        shared = set(self.keys) & set(other.keys)
        if shared:
            return all(self.keys[key] == other.keys[key] for key in shared)
        return not self.id and not other.id and self.label == other.label


class SessionLookup(SystemModel):
    tool: str
    summary: str                           # code dựng: bảng, cột lọc (không giá trị), tổng
    total: int | None = None
    turn: int = 0


class ToolMemory(SystemModel):
    """Phần một output tool để lại cho phiên (tool tự trích bằng hàm thuần)."""

    entities: list[SessionEntity] = Field(default_factory=list)
    lookup: SessionLookup | None = None
    is_list: bool = False                  # output là danh sách có thứ tự (ordinal hợp lệ)


class SessionFacts(SystemModel):
    turn: int = 0                          # số lượt agent đã ghi facts
    owner: str | None = None               # acting_user_id của phiên khi ghi; đổi người thì xoá
    entities: list[SessionEntity] = Field(default_factory=list, max_length=MAX_ENTITIES)
    lookups: list[SessionLookup] = Field(default_factory=list, max_length=MAX_LOOKUPS)
    # Lượt trước kết thúc bằng câu hỏi làm rõ hoặc dừng sớm (final_reason của lượt đó).
    pending_reason: str | None = None
