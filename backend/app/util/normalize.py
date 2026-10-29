


from dataclasses import dataclass
import unicodedata


@dataclass(frozen=True, slots=True)
class NormalizedInput:
    """Các phiên bản văn bản phục vụ kiểm tra an toàn."""

    original_text: str
    nfc_text: str
    casefolded_text: str
    accent_folded_text: str


def normalize_nfc(text: str) -> str:
    """Chuẩn hóa Unicode về dạng NFC."""
    return unicodedata.normalize("NFC", text)


def make_casefold_view(text: str) -> str:
    """
    Tạo bản đối chiếu không phân biệt chữ hoa/chữ thường.
    Không dùng bản này để thay thế nội dung hiển thị.
    """
    nfc_text = normalize_nfc(text)
    return unicodedata.normalize("NFC", nfc_text.casefold())


def make_accent_folded_view(text: str) -> str:
    """
    Tạo bản đối chiếu bỏ dấu cho việc dò tìm biến thể tiếng Việt.

    Ví dụ:
        'Đặng Thị Hương' -> 'dang thi huong'

    Chỉ dùng để phát hiện, không dùng thay nội dung gốc.
    """
    decomposed = unicodedata.normalize("NFD", text.casefold())

    result: list[str] = []

    for char in decomposed:
        # Đ/đ không được loại dấu bằng cách bỏ combining marks.
        if char == "đ":
            result.append("d")
        elif unicodedata.category(char) not in {"Mn", "Mc", "Me"}:
            result.append(char)

    return "".join(result)


def normalize_for_detection(text: str) -> NormalizedInput:
    """Tạo các bản văn bản phục vụ những detector an toàn."""
    nfc_text = normalize_nfc(text)
    casefolded_text = make_casefold_view(nfc_text)
    accent_folded_text = make_accent_folded_view(casefolded_text)

    return NormalizedInput(
        original_text=text,
        nfc_text=nfc_text,
        casefolded_text=casefolded_text,
        accent_folded_text=accent_folded_text,
    )

# Dấu chỉ tiếng Việt dùng (hỏi, nặng, móc, trăng) và chữ đ; dấu sắc/huyền/ngã/mũ
# cũng có trong tiếng Pháp, Bồ Đào Nha... nên không dùng để phân biệt.
_VIETNAMESE_MARKS = frozenset({"̉", "̣", "̛", "̆"})
# Từ có dấu thường gặp nhưng không mang dấu đặc trưng ở trên ("Có ai không?").
_VIETNAMESE_WORDS = frozenset({
    "có", "không", "là", "gì", "và", "cho", "này", "nào", "với", "máy", "cần",
    "tôi", "bạn", "anh", "chị", "em", "thế", "như", "nhé", "ạ", "ơi",
})


def guess_reply_language(text: str) -> str:
    """Đoán ngôn ngữ trả lời khi chưa có nguồn nào khác: 'vi' nếu có dấu đặc trưng
    hoặc từ thông dụng tiếng Việt, ngược lại 'en'. Không dùng thay cho ngôn ngữ do
    analysis phát hiện."""
    folded = unicodedata.normalize("NFC", text.casefold())
    decomposed = unicodedata.normalize("NFD", folded)
    if "đ" in folded or any(char in _VIETNAMESE_MARKS for char in decomposed):
        return "vi"
    words = "".join(char if char.isalpha() else " " for char in folded).split()
    return "vi" if any(word in _VIETNAMESE_WORDS for word in words) else "en"
