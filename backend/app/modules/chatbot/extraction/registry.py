

from __future__ import annotations
 
import difflib
import re
from typing import Any
 
MAX_SUB_QUERIES = 3
MAX_CANDIDATES = 3
# Tìm model theo tiêu chí: tối đa bấy nhiêu model thì agent tự tra tiếp từng model,
# nhiều hơn thì hỏi nhân viên chọn.
MAX_AUTO_LOOKUP_MODELS = 3
FUZZY_CUTOFF = 0.6
DOMAINS = ("technical_docs", "company_info", "product_catalog")
SCOPES = ("installation", "operation", "configuration", "maintenance")
MODEL_POLICIES = ("none", "optional", "required")
NO_TARGET_ROUTES = ("handoff", "chitchat", "out_of_scope")
 
# [C11] Câu nhắc mã cụ thể (connector CN1/X40, tham số #4130, alarm AL12/E05) luôn
# phụ thuộc model, bất kể LLM đánh dấu model_dependency thế nào.
MODEL_SPECIFIC_PATTERN = re.compile(r"(?<![a-z0-9])(?:cn\d+|x\d+|#\d+|al\d+|e\d{2,})(?![a-z0-9])", re.I)

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
    # allow_general    : [C11] mặc định True; False = không chấp nhận model_dependency
    #                    "general" của LLM, thiếu model thì luôn kế thừa/hỏi lại.
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
            "allow_general": False,        # đấu dây/chân connector luôn phụ thuộc model
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
            "allow_general": False,        # mã lỗi/alarm luôn phụ thuộc model
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
    # Mã canonical = `product_name` của CRM (danh mục đầy đủ), để báo cáo CRM và tra cứu
    # tài liệu dùng chung một mã. Model chưa có alias chính thức dùng chính mã làm tên.
    "product_models": [
        "F54", "F86", "F86E", "F10T", "6AH", "6AHE", "6AV", "6AVE", "10iV", "10iVE",
    ],
    # So khớp bỏ qua hoa/thường, khoảng trắng, "_" và "-": "Astro 6AH" cũng nhận mã cũ ASTRO_6AH.
    "aliases": {
        "Astro 6AH": "6AH",
        "Astro 6AV": "6AV",
    },
    "ambiguous_aliases": {
        "10i": ["10iV", "10iVE"], "Astro 10i": ["10iV", "10iVE"],
        "Astro 10": ["10iV", "10iVE"],
        "Astro 6A": ["6AH", "6AHE", "6AV", "6AVE"],
        "6A": ["6AH", "6AHE", "6AV", "6AVE"],
        "Astro": ["6AH", "6AHE", "6AV", "6AVE", "10iV", "10iVE"],
    },
    # Tên hiển thị khi hỏi lại/nút bấm; model không có ở đây hiển thị bằng mã.
    "display_names": {
        "6AH": "Astro 6AH",
        "6AV": "Astro 6AV",
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

    # ------------------------------------------------------------- capabilities
    # Phần cứng HỖ TRỢ gì (khác coverage: có TÀI LIỆU gì). Closed world: mọi model
    # đều có một dòng; interface không liệt kê nghĩa là không hỗ trợ. Dùng để tìm
    # model theo tiêu chí bằng code thay vì đọc văn bản RAG.
    # TẠM: F86E/6AHE/6AVE lấy theo model gốc, 10iV/10iVE theo dòng 10i cũ; chưa có dữ
    # liệu chính thức (xem docs/ai/current-state.md).
    "capabilities": {
        "control_interface": {
            "F54": ["pulse_train"],
            "F86": ["pulse_train", "ethercat"],
            "F86E": ["pulse_train", "ethercat"],
            "F10T": ["pulse_train", "ethercat"],
            "6AH": ["pulse_train", "ethercat", "mechatrolink"],
            "6AHE": ["pulse_train", "ethercat", "mechatrolink"],
            "6AV": ["pulse_train", "ethercat", "mechatrolink"],
            "6AVE": ["pulse_train", "ethercat", "mechatrolink"],
            "10iV": ["pulse_train", "ethercat", "mechatrolink"],
            "10iVE": ["pulse_train", "ethercat", "mechatrolink"],
        },
    },

    # ----------------------------------------------------------------- coverage
    # None            : không phụ thuộc model
    # list[model]     : model có dữ liệu
    # dict[model, ifs]: [C7] model có dữ liệu, chỉ cho các control_interface liệt kê
    "coverage": {
        # Theo doc_chunks sau backend/sql/migrate_product_models_crm.sql (ASTRO_10I -> 10iV).
        "product_catalog": ["F54", "F86", "F10T", "6AH", "6AV", "10iV"],
        "technical_docs": {"F86": ["pulse_train", "ethercat"]},
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