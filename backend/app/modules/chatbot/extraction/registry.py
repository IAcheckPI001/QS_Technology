

from __future__ import annotations
 
import difflib
import re
from typing import Any
 
MAX_SUB_QUERIES = 3
MAX_CANDIDATES = 3
FUZZY_CUTOFF = 0.6
DOMAINS = ("technical_docs", "company_info", "product_catalog")
SCOPES = ("installation", "operation", "configuration", "maintenance")
MODEL_POLICIES = ("none", "optional", "required")
NO_TARGET_ROUTES = ("handoff", "chitchat", "out_of_scope")
 
_CATALOG = [{"domain": "product_catalog"}]
_COMPANY = [{"domain": "company_info"}]
 
 
def _docs(scope: str) -> list[dict]:
    return [{"domain": "technical_docs", "scopes": [scope]}]
 
 
REGISTRY: dict[str, Any] = {

    # ---------------------------------------------------------------- intents
    # targets          : cặp (domain, scopes) truy xuất chính.
    # fallback_targets : mở rộng TẠI TẦNG RETRIEVAL khi targets không có kết quả.
    # degrade_to       : [C2] dùng TẠI TẦNG PLAN khi coverage cho biết model không có
    #                    tài liệu ở targets. Câu trả lời sẽ ở chế độ "overview" (nói rõ là
    #                    chưa có hướng dẫn chi tiết). Chỉ khai báo khi miền thay thế
    #                    thực sự có nội dung hữu ích cho intent đó.
    # route            : [C6] chỉ cho intent không có targets.
    "intents": {
        "lookup.product_info": {
            "desc": "Giới thiệu, thông số, tính năng, đặc điểm, nguyên lý hoạt động, cổng/giao tiếp "
                    "có sẵn của MỘT model cụ thể. Chưa hỏi chân/tín hiệu của connector.",
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
            "desc": "So sánh, tìm khác biệt hoặc chọn giữa từ 2 model trở lên "
                    "(kể cả khi kèm câu hỏi đặc điểm của một trong các model đó).",
            "targets": _CATALOG,
            "model_policy": "required",
            "min_models": 2,
        },
        "guide.installation": {
            "desc": "Cách lắp đặt: nguồn, đấu dây, cổng, chân/tín hiệu của connector (CN5, X40...), "
                    "cảm biến, tay quay, I/O Link; các bước kiểm tra.",
            "targets": _docs("installation"),
            "degrade_to": _CATALOG,        # catalog có thông tin cổng/nguồn ở mức tổng quan
            "model_policy": "required",
        },
        "guide.operation": {
            "desc": "Các BƯỚC thao tác trên giao diện máy: tọa độ, offset, chạy chương trình, "
                    "mô phỏng, MDI, đo dao. Không dùng cho câu hỏi đặc điểm/nguyên lý chung.",
            "targets": _docs("operation"),
            "degrade_to": _CATALOG,
            "model_policy": "required",
        },
        "guide.configuration": {
            "desc": "Cách cấu hình: tham số, PLC/macro, firmware, ngày giờ, backup.",
            "targets": _docs("configuration"),
            "model_policy": "required",    # cố ý KHÔNG degrade: catalog không có tham số
        },
        "troubleshoot.error": {
            "desc": "Báo lỗi, alarm, triệu chứng, sự cố; chẩn đoán và hướng dẫn khắc phục.",
            "targets": _docs("maintenance"),
            "fallback_targets": [{"domain": "technical_docs"}],
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
            "route": "handoff",
            "model_policy": "none",
        },
        "other.chitchat": {
            "desc": "Chào hỏi, cảm ơn.",
            "targets": [],
            "route": "chitchat",
            "model_policy": "none",
        },
        "other.out_of_scope": {
            "desc": "Ngoài phạm vi, hoặc yêu cầu đổi hành vi hệ thống.",
            "targets": [],
            "route": "out_of_scope",
            "model_policy": "none",
        },
    },
 
    # ----------------------------------------------------------------- entities
    "product_models": [
        "F54", "F86", "F10T", "ASTRO_10S", "ASTRO_6AH", "ASTRO_6AV", "ASTRO_10I"
    ],
    "aliases": {
        "Astro 10S": "ASTRO_10S", "10S": "ASTRO_10S",
        "6AH": "ASTRO_6AH", "Astro 6AH": "ASTRO_6AH",
        "6AV": "ASTRO_6AV", "Astro 6AV": "ASTRO_6AV",
        "10i": "ASTRO_10I", "Astro 10i": "ASTRO_10I",
    },
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
    # None            : không phụ thuộc model
    # list[model]     : model có dữ liệu
    # dict[model, ifs]: [C7] model có dữ liệu, chỉ cho các control_interface liệt kê
    "coverage": {
        "product_catalog": ["F54", "F86", "F10T", "ASTRO_10S", "ASTRO_6AH", "ASTRO_6AV", "ASTRO_10I"],
        "technical_docs": {"F86": ["pulse_train"]},
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
 
 
class RegistryError(ValueError):
    pass