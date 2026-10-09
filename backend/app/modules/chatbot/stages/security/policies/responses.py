from typing import Final


DEFAULT_LOCALE: Final = "en"
SUPPORTED_LOCALES: Final = frozenset({"en", "vi"})

SECURITY_RESPONSES: Final = {
    "request_blocked": {
        "en": "This request is outside the supported scope. Please ask about our CNC products and consulting services.",
        "vi": "Dạ thông tin nằm ngoài phạm vi hỗ trợ, anh/chị cần hướng dẫn tư vấn về các sản phẩm CNC ạ?",
    },
}


def normalize_locale(locale: str | None) -> str:
    if not locale:
        return DEFAULT_LOCALE
    language = locale.strip().lower().replace("_", "-").split("-", 1)[0]
    return language if language in SUPPORTED_LOCALES else DEFAULT_LOCALE


def get_response_message(code: str, locale: str | None) -> str:
    messages = SECURITY_RESPONSES.get(code)
    if messages is None:
        raise KeyError(f"Unknown response code: {code}")
    return messages[normalize_locale(locale)]
