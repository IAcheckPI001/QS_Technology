"""Nhóm bảng theo nghiệp vụ (đưa vào description của tool) và ghi chú nghĩa của bảng chính.

Viết tay từ `docs/ai/tool_instruction/prompt_tool_report` (gợi ý bảng, giả định thường
gặp), `ai-reporting-query.md` và định nghĩa của catalog cũ (`reporting/datasets/`). Từ
2026-11-12 CRM tự mô tả bảng/cột/quan hệ (crm_schema trả nguyên): ghi chú ở đây chỉ giữ
phần CRM không nói (cách hiểu câu hỏi nghiệp vụ, đường join, quy ước của dịch vụ AI). Test
kiểm tra mọi bảng truy vấn được nằm trong đúng một nhóm và mọi tên bảng ở đây có trong index.
"""

from dataclasses import dataclass

@dataclass(frozen=True)
class LookupSpec:
    """Bảng tra cứu nhỏ do admin tạo (không phải enum, ít đổi): crm_schema lấy giá trị thật.

    columns: cột đầu là giá trị dùng để lọc, các cột sau là nhãn để LLM so với từ trong câu hỏi.
    filters: điều kiện của CRM Reporting API (vd chỉ vai trò hệ thống).
    """

    columns: tuple[str, ...]
    filters: tuple[dict[str, str], ...] = ()


LOOKUP_TABLES: dict[str, LookupSpec] = {
    # Vai trò phân quyền; vai trò kind=product do khách tự tạo cho máy của họ, không phải nhân viên.
    "roles": LookupSpec(("code", "name"), ({"field": "kind", "op": "eq", "value": "system"},)),
    "customer_statuses": LookupSpec(("name", "label_vi")),
    "customer_status_groups": LookupSpec(("name", "label_vi", "stage")),
    "customer_groups": LookupSpec(("name", "label_vi")),
    "business_fields": LookupSpec(("name", "label_vi")),
}

@dataclass(frozen=True)
class DefaultFilter:
    """Điều kiện compile tự thêm khi LLM không tự lọc trên `field` (bất kỳ op nào).

    Dùng cho định nghĩa nghiệp vụ mà model nhỏ hay bỏ qua dù guide đã nêu (eval 2026-11-12:
    gpt-4o-mini bỏ `user_id.is_active` 9/9 lần). LLM bỏ điều kiện bằng `include_inactive=true` của
    RawQuery (lọc chính `field` theo cách khác cũng được; eval cho thấy model nhỏ không tự làm).
    """

    field: str
    op: str
    value: str
    reason: str


DEFAULT_FILTERS: dict[str, tuple[DefaultFilter, ...]] = {
    # Toma 2026-11-12: nhân viên theo vai trò = người được gán vai trò, chỉ tài khoản còn dùng.
    "user_roles": (
        DefaultFilter("user_id.is_active", "eq", "true", "mặc định: chỉ tài khoản còn dùng"),
    ),
    # Toma 2026-11-12: "khách hàng" không tính khách spam (khách lost vẫn tính); khách đã xoá/đã
    # gộp do dataset customers của CRM tự loại.
    "customers": (
        DefaultFilter("customer_type", "neq", "spam", "mặc định: không tính khách spam"),
    ),
}

# Filter trạng thái hiện tại bị bỏ khi query có date_range (hỏi phát sinh trong kỳ thì tính cả bản
# ghi đã chuyển/đã kết thúc). Toma 2026-11-12, eval q13: LLM thêm is_current khi đếm lần giao trong
# tháng 10 → bỏ sót phiếu đã chuyển cho người khác (25 → 21).
DROP_WITH_DATE_RANGE: dict[str, tuple[str, ...]] = {
    "support_assignments": ("is_current",),
}

TABLE_GROUPS: dict[str, tuple[str, ...]] = {
    "Khách hàng, sale, marketing": (
        "customers", "customer_statuses", "customer_status_groups", "customer_groups",
        "customer_customer_groups", "customer_business_fields", "business_fields", "customer_logs",
        "customer_views", "customer_new_interactions", "customer_team_members", "activities",
        "leads", "students", "contact_messages", "campaigns", "campaign_registrations",
        "campaign_visits", "sales_round_robin_state",
    ),
    "Sản phẩm, thiết bị (máy) của khách": (
        "products", "product_items", "product_item_aliases", "product_item_logs",
        "product_ownerships", "product_ownership_transfer_requests", "product_agents",
        "product_user_access", "product_item_activation_requests", "product_item_recall_requests",
        "product_item_return_requests", "product_support_limits", "lock_requests", "iot_devices",
        "iot_firmwares", "iot_firmware_updates", "issue_reports", "service_logs",
    ),
    "Hỗ trợ khách (phiếu hỗ trợ)": (
        "support_cases", "support_assignments", "support_case_events", "support_messages",
        "support_attachments", "support_appointments", "support_cancel_requests", "support_ratings",
        "support_time_entries", "support_entitlements", "support_entitlement_transactions",
        "support_waiting_messages", "support_waiting_message_events",
        "support_waiting_message_helpers", "support_waiting_message_replies",
        "support_waiting_message_views", "request_comments",
    ),
    "Mua hàng, kho": (
        "suppliers", "materials", "material_suppliers", "material_serial_lots",
        "purchase_requisitions", "purchase_requisition_items", "purchase_orders",
        "purchase_order_items", "po_backorders", "po_goods_receipts", "goods_receipts",
        "goods_receipt_items", "goods_issues", "goods_issue_items", "goods_returns",
        "goods_return_items", "stock", "stock_movements", "stocktakes", "stocktake_lines",
        "warehouses",
    ),
    "Sản xuất": (
        "boms", "bom_components", "manufacturing_work_orders", "work_orders", "wo_operations",
        "work_order_comments", "material_consumptions", "material_serial_lot_consumptions",
        "finished_goods_receipts", "finished_goods_receipt_items", "qc_records",
    ),
    "Dự án, công việc": (
        "projects", "phases", "project_members", "project_assets", "project_asset_components", "tasks",
    ),
    "Tài liệu, file": (
        "company_doc_nodes", "company_doc_node_versions", "company_doc_node_products",
        "manualhub_documents", "manualhub_document_versions", "manualhub_activities", "files",
        "file_links",
    ),
    "Người dùng, tổ chức, phân quyền": (
        "auth_users", "user_profiles", "user_organizations", "user_roles", "user_permissions",
        "roles", "role_permissions", "permissions", "roles_owner_scope_rollback",
        "organizations", "rbac_audit_logs",
    ),
    "Chat nội bộ, thông báo": (
        "chat_conversations", "chat_messages", "chat_participants", "notifications",
        "notification_delivery_log",
    ),
}

TABLE_NOTES: dict[str, str] = {
    "customers": (
        "Dataset dựng sẵn: CRM tự loại khách đã xoá, đã gộp và khách đại diện tổ chức; cần quyền "
        "customer.read (bảng khác cần auth.manage_roles). Ngoài cột thật còn có dimension riêng: "
        "assigned_sales (UUID sale), status, campaign, organization, created_day/created_month/"
        "created_year. Hệ thống tự loại khách spam (customer_type neq spam); hỏi về khách spam thì tự "
        "lọc customer_type, hỏi kể cả spam thì include_inactive=true. Sale phụ trách: "
        "assigned_sales_id (UUID tài khoản); username của sale: assigned_sales_id.username; họ tên "
        "sale không join tới được (xem person_filter). 'Khách của nhân viên X' = đếm/liệt kê theo "
        "assigned_sales_id, không lọc ngày trừ khi câu hỏi nêu kỳ."
    ),
    "support_cases": (
        "Phiếu hỗ trợ. 'đã xong' = status resolved/closed; 'đang mở' = new/pending/in_progress/"
        "reopened. Khách của phiếu = product_item_id.customer_id: là khách ĐANG giữ máy, máy đã "
        "chuyển chủ thì khác khách lúc mở phiếu (nói rõ khi trả lời về phiếu cũ). Phiếu không có máy "
        "thì không có khách; tổ chức mở phiếu: customer_organization_id. Model máy: "
        "product_item_id.product_id.name."
    ),
    "support_assignments": (
        "Mỗi dòng là một lần giao phiếu cho người xử lý: assigned_to → auth_users, case_id → "
        "support_cases, created_at = lúc giao. Việc đang xử lý bây giờ (không có kỳ): filter "
        "is_current eq true. Có kỳ thời gian: tính mọi lần giao trong kỳ (hệ thống bỏ is_current). "
        "'Nhân viên X hỗ trợ bao nhiêu "
        "khách' = metric count_distinct:case_id.product_item_id.customer_id. X là username: "
        "assigned_to.username; X là tên người: lấy user_id ở user_profiles trước."
    ),
    "product_ownerships": (
        "Thiết bị giao cho khách (không có bảng đơn bán hàng: 'bán được' = bản ghi ở đây, created_at "
        "= ngày giao; KHÔNG lọc deleted_at vì đó là lúc kết thúc sở hữu). Loại chuyển nhượng giữa "
        "khách: filter transferred_from_ownership_id is_null. Chủ hiện tại: is_current eq true. "
        "Khách: owner_customer_id → customers; model: product_item_id.product_id.name."
    ),
    "product_items": (
        "Từng máy cụ thể (serial: code): product_id → products (model: name), customer_id → khách "
        "đang giữ máy (trống khi máy ở kho QS hoặc đã thu hồi)."
    ),
    "user_roles": (
        "Vai trò phân quyền gán cho người dùng (admin tạo vai trò để gom nhóm/phân quyền, ít đổi; một "
        "người có thể có nhiều vai trò). 'Nhân viên <vai trò>' = người được gán vai trò đó: nhân viên "
        "sales = được gán vai trò có code sales (admin có quyền sales nhưng không tính là nhân viên "
        "sales). Đếm người: metric count_distinct:user_id. Hệ thống tự thêm filter user_id.is_active "
        "eq true (chỉ tài khoản còn dùng); hỏi kể cả người đã nghỉ/không còn dùng thì đặt "
        "include_inactive=true. Mã vai trò: lấy ở known_values (role_id.code)."
    ),
    "auth_users": (
        "Gồm cả tài khoản khách hàng (vai trò customer) và đại lý, không chỉ nhân viên: KHÔNG đếm bảng "
        "này để trả lời số nhân viên (dùng user_roles). "
        "Tài khoản đăng nhập: username, email, phone, region. is_active: true = đang dùng, false = "
        "không còn dùng. Tra người hoặc liệt kê nhân viên HIỆN TẠI: filter is_active eq true; thống kê "
        "lịch sử (ai đã xử lý, đã tạo...) không lọc, người không còn dùng vẫn được tính, ghi chú khi "
        "trả lời. Không có họ tên và không có quan hệ đi ra; họ tên ở user_profiles, vai trò ở "
        "user_roles, tổ chức ở user_organizations: lấy các bảng đó làm dataset."
    ),
    "user_profiles": (
        "Họ tên người dùng: tên gọi ở first_name (vd 'Hiếu'), họ và tên đệm ở last_name; "
        "user_id.username để nối với tài khoản, user_id.is_active = tài khoản còn dùng. Tra nhân viên "
        "theo tên: dataset user_profiles, filter first_name contains (không ra thì thử last_name). "
        "user_id là UUID dùng để lọc mọi cột khoá ngoại trỏ tới auth_users ở bảng khác "
        "(assigned_sales_id, assigned_to, created_by...)."
    ),
    "activities": (
        "Lịch sử chăm sóc của sale: sales_id → auth_users, action, content, contact_at; "
        "activityable_type (lead/customer) + activityable_id là đối tượng (không join được)."
    ),
    # Ghi chú chỉ liệt kê cột đã bỏ (2026-11-12): CRM mô tả bảng và cột qua /reports/datasets
    # và /reports/tables; ở đây chỉ giữ nghĩa nghiệp vụ CRM không mô tả.
    "leads": "Khách tiềm năng đăng ký từ form/chiến dịch (khác bảng customers).",
    "students": "Học viên đăng ký (khác bảng customers): full_name, status, deposit_agreed.",
    "organizations": "Tổ chức, chi nhánh, đại lý (agent_type khác null là đại lý); parent_id là tổ chức cha.",
    "lock_requests": (
        "Yêu cầu khoá/mở khoá máy: product_item_id, requester_id, status, reason, approved_by, "
        "resolved_at. Khoá mở máy (unlock_key) và mã thiết bị (device_input) bị ẩn."
    ),
}
