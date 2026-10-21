"""Fixed replies for turns that do not need the answer LLM."""

from typing import Final

from app.modules.chatbot.stages.security.policies.responses import (
    SUPPORTED_LOCALES,
    normalize_locale,
)

DIRECT_RESPONSES: Final = {
    "chitchat": {
        "vi": "Dạ em chào anh/chị! Em là trợ lý hỗ trợ kỹ thuật CNC của QS Technology. Anh/chị cần hỗ trợ về bộ điều khiển, lắp đặt, vận hành hay xử lý lỗi ạ?",
        "en": "Hello! I'm the QS Technology CNC support assistant. How can I help with your controller, installation, operation or troubleshooting?",
    },
    "out_of_scope": {
        "vi": "Dạ nội dung này nằm ngoài phạm vi hỗ trợ của em. Em có thể hỗ trợ anh/chị về bộ điều khiển CNC, lắp đặt, vận hành, cấu hình và xử lý lỗi ạ.",
        "en": "That is outside what I can help with. I can support you with CNC controllers, installation, operation, configuration and troubleshooting.",
    },
    "handoff.pricing": {
        "vi": "Dạ về giá và báo giá, em sẽ chuyển anh/chị tới nhân viên kinh doanh để được tư vấn chính xác ạ.",
        "en": "For pricing and quotations, I will connect you with our sales team.",
    },
    "handoff.warranty": {
        "vi": "Dạ về chế độ bảo hành, em sẽ chuyển anh/chị tới nhân viên phụ trách để được hỗ trợ ạ.",
        "en": "For warranty questions, I will connect you with our support staff.",
    },
    "handoff.policy": {
        "vi": "Dạ về chính sách, em sẽ chuyển anh/chị tới nhân viên phụ trách để được giải đáp chính xác ạ.",
        "en": "For policy questions, I will connect you with our staff.",
    },
    "handoff.purchase": {
        "vi": "Dạ về việc mua hàng, em sẽ chuyển anh/chị tới nhân viên kinh doanh để hỗ trợ ạ.",
        "en": "For purchasing, I will connect you with our sales team.",
    },
    "handoff.shipping": {
        "vi": "Dạ về giao hàng, em sẽ chuyển anh/chị tới nhân viên phụ trách để hỗ trợ ạ.",
        "en": "For shipping, I will connect you with our staff.",
    },
    "handoff.human_request": {
        "vi": "Dạ em sẽ chuyển anh/chị tới nhân viên hỗ trợ ngay ạ.",
        "en": "I will connect you with a staff member.",
    },
    "agent.awaiting": {
        "vi": "Dạ yêu cầu của anh/chị đã được chuyển tới nhân viên, anh/chị vui lòng chờ trong giây lát ạ.",
        "en": "Your request has been forwarded to our staff. Please wait a moment.",
    },
    "agent.active": {
        "vi": "Dạ anh/chị đang trao đổi với nhân viên hỗ trợ ạ.",
        "en": "You are chatting with our support staff.",
    },
}


def get_direct_response(code: str, locale: str | None, language: str = "vi") -> str:
    """Use the client locale when sent, otherwise the detected query language."""
    messages = DIRECT_RESPONSES.get(code)
    if messages is None:
        raise KeyError(f"Unknown direct response code: {code}")
    resolved = normalize_locale(locale) if locale else language.split("-", 1)[0]
    return messages[resolved if resolved in SUPPORTED_LOCALES else "vi"]
