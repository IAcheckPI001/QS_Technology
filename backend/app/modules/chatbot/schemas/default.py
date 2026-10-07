

"""Kiểu dữ liệu và model dùng chung giữa hợp đồng công khai (schemas/) và nội bộ (system/)."""
 
from typing import Annotated
 
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

SCHEMA_VERSION = "1.0"
MAX_MESSAGE_CHARS = 4000

# ---------------------------------------------------------------------------
# Cấu hình các kiểu tái sử dụng: thay cho việc viết field_validator strip/blank ở từng model.
# ---------------------------------------------------------------------------
NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
Identifier = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=128)]
SourceId = Annotated[str, StringConstraints(pattern=r"^S\d+$")]  # S1, S2 ... (phạm vi hội thoại)
LanguageCode = Annotated[str, StringConstraints(pattern=r"^[a-z]{2}(-[A-Z]{2})?$")]
NonNegInt = Annotated[int, Field(ge=0)]
Probability = Annotated[float, Field(ge=0.0, le=1.0)]
MessageText = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_MESSAGE_CHARS)
]

# ---------------------------------------------------------------------------
# Cấu hình base model: bỏ qua trường lạ cho inbound, chặt chẽ cho outbound
# ---------------------------------------------------------------------------
class InboundModel(BaseModel):
    """Dữ liệu từ bên ngoài: bỏ qua trường lạ để CRM thêm field không bị 422."""
 
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)
 
 
class OutboundModel(BaseModel):
    """Dữ liệu trả ra ngoài: chặt chẽ, không lọt trường nội bộ."""
 
    model_config = ConfigDict(extra="forbid")

class SystemModel(BaseModel):
    """Dữ liệu hệ thống: forbid để bắt lỗi gõ sai tên trường sớm,
    validate_assignment để stage gán sai kiểu là lỗi ngay."""
 
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

# ---------------------------------------------------------------------------
# Metadata của tài liệu nguồn – dùng ở trace, history và citation.
# ---------------------------------------------------------------------------
class SourceMetadata(SystemModel):
    doc_id: Identifier                      # bắt buộc: định danh nguồn
    version: Annotated[int, Field(ge=1)]    # bắt buộc: phân biệt bản tài liệu
    title: str | None = None
    page: Annotated[int, Field(ge=1)] | None = None
    section: str | None = None
    url: str | None = None

class PublicSourceMetadata(SourceMetadata):
    """Bản trả cho CRM: title bắt buộc để luôn có gì đó hiển thị.
    Finalize chịu trách nhiệm điền giá trị dự phòng."""
 
    model_config = ConfigDict(extra="forbid")
 
    title: NonEmptyStr