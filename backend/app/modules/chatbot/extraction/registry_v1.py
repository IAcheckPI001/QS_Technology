


from __future__ import annotations
 
import re
from typing import Any

MAX_SUB_QUERIES = 3
DOMAINS = ("technical_docs", "company_info", "product_catalog")
SCOPES = ("installation", "operation", "configuration", "maintenance")
MODEL_POLICIES = ("none", "optional", "required")

_CATALOG = [{"domain": "product_catalog"}]
_COMPANY = [{"domain": "company_info"}]

def _docs(scope: str) -> list[dict]:
    return [{"domain": "technical_docs", "scopes": [scope]}]

REGISTRY: dict[str, Any] = {
    "intents": {
        "lookup.product_info": {
            "desc": "Giới thiệu, thông số, tính năng, cổng/giao tiếp có sẵn của MỘT model cụ thể. "
                    "Chưa hỏi chân/tín hiệu của connector.",
            "targets": _CATALOG,
            "model_policy": "required",
        },
        "lookup.product_catalog": {
            "desc": "Liệt kê/duyệt danh mục: có những model, phiên bản, servo, board mở rộng, "
                    "phụ kiện nào; tìm dòng phù hợp theo tiêu chí khi chưa chốt model.",
            "targets": _CATALOG,
            "model_policy": "optional",
        },
        "compare.product_models": {
            "desc": "So sánh, tìm khác biệt hoặc chọn giữa từ 2 model trở lên.",
            "targets": _CATALOG,
            "model_policy": "required",
            "min_models": 2,
        },
        "guide.installation": {
            "desc": "Cách lắp đặt: nguồn, đấu dây, cổng, chân/tín hiệu của connector (CN5, X40...), "
                    "cảm biến, tay quay, I/O Link; các bước kiểm tra.",
            "targets": _docs("installation"),
            "model_policy": "required",
        },
        "guide.operation": {
            "desc": "Cách thao tác giao diện: tọa độ, offset, chạy chương trình, mô phỏng, MDI, đo dao.",
            "targets": _docs("operation"),
            "model_policy": "required",
        },
        "guide.configuration": {
            "desc": "Cách cấu hình: tham số, PLC/macro, firmware, ngày giờ, backup.",
            "targets": _docs("configuration"),
            "model_policy": "required",
        },
        "troubleshoot.error": {
            "desc": "Báo lỗi, alarm, triệu chứng, sự cố; chẩn đoán và hướng dẫn khắc phục.",
            "targets": _docs("maintenance"),
            "fallback_targets": [{"domain": "technical_docs"}],   # mọi scope
            "model_policy": "required",
        },
        "lookup.company_info": {
            "desc": "Công ty: địa chỉ, liên hệ, lịch sử, mảng kinh doanh, nâng cấp máy cũ, "
                    "máy do QS chế tạo.",
            "targets": _COMPANY,
            "model_policy": "none",
        },
        "handoff.human": {
            "desc": "Giá, báo giá, bảo hành, chính sách, mua hàng, giao hàng, hoặc đòi gặp người thật.",
            "targets": [],
            "model_policy": "none",
        },
        "other.chitchat": {
            "desc": "Chào hỏi, cảm ơn.",
            "targets": [],
            "model_policy": "none",
        },
        "other.out_of_scope": {
            "desc": "Ngoài phạm vi, hoặc yêu cầu đổi hành vi hệ thống.",
            "targets": [],
            "model_policy": "none",
        },
    },
    # ----------------------------------------------------------------- entities
    "product_models": [
        "F54", "F86", "F10T", "ASTRO_10S", "ASTRO_6AH", "ASTRO_6AV", "ASTRO_10I",
    ],
    # alias KHÔNG mơ hồ -> mã canonical (mã canonical tự động là alias của chính nó)
    "aliases": {
        "Astro 10S": "ASTRO_10S", "10S": "ASTRO_10S",
        "6AH": "ASTRO_6AH", "Astro 6AH": "ASTRO_6AH",
        "6AV": "ASTRO_6AV", "Astro 6AV": "ASTRO_6AV",
        "10i": "ASTRO_10I", "Astro 10i": "ASTRO_10I",
    },
    # cách gọi MƠ HỒ -> danh sách ứng viên (giả định cần QS xác nhận). Luôn hỏi lại.
    "ambiguous_aliases": {
        "Astro 6A": ["ASTRO_6AH", "ASTRO_6AV"],
        "6A": ["ASTRO_6AH", "ASTRO_6AV"],
        "Astro 10": ["ASTRO_10S", "ASTRO_10I"],
        "Astro": ["ASTRO_10S", "ASTRO_6AH", "ASTRO_6AV", "ASTRO_10I"],
    },
    "control_interface": {
        "pulse_train": "Pulse Train/xung",
        "ethercat": "EtherCAT",
        "mechatrolink": "Mechatrolink",
    },
    # key = enum ; value = gợi ý từ khóa tiếng Việt (đưa vào prompt). Đã bỏ "interface" (trùng control_interface)
    "spec_attributes": {
        "dimension": "kích thước",
        "monitor_size": "màn hình",
        "max_axis": "số trục",
        "io": "ngõ vào/ra I/O",
        "loop_type": "open/closed loop",
        "look_ahead": "look-ahead",
        "spindle": "trục chính",
        "rtcp": "RTCP",
        "ports": "cổng USB/RS485/MPG",
    },
    "handoff_reasons": [
        "pricing", "warranty", "policy", "purchase", "shipping", "human_request",
    ],
 
    # ----------------------------------------------------------------- coverage
    # Model nào có dữ liệu ở miền nào. None = không phụ thuộc model.
    "coverage": {
        "product_catalog": ["F54", "F86", "F10T", "ASTRO_10S", "ASTRO_6AH", "ASTRO_6AV", "ASTRO_10I"],
        "technical_docs": ["F86"],            # chỉ bản Pulse Train của F86
        "company_info": None,
    },
 
    # Thứ tự ưu tiên khi nhiều lý do cùng đúng (cụ thể -> chung)
    "clarification_order": [
        "ambiguous_product_model",
        "unknown_product_model",
        "context_conflict",
        "insufficient_models_for_comparison",
        "missing_product_model",
    ],
}