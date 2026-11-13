"""Index schema CRM, SINH TỰ ĐỘNG: không sửa tay.

Nguồn: docs/ai/tool_instruction/database-structure.sql (pg_dump, started on 2026-11-10 07:07:51 UTC).
Sinh lại: `.\\venv\\Scripts\\python.exe scripts\\build_crm_schema_index.py` (thư mục backend).
"""

from .schema import TableIndex

TABLES: dict[str, TableIndex] = {
    "activities": TableIndex(
        columns={
            "id": "uuid", "activityable_type": "text", "activityable_id": "uuid",
            "sales_id": "uuid", "action": "text", "content": "text", "contact_at": "timestamp",
            "created_at": "timestamp",
        },
        relations={
            "sales_id": "auth_users",
        },
        values={
            "activityable_type": ("lead", "customer"),
        },
    ),
    "app_settings": TableIndex(
        columns={
            "key": "text", "value": "text",
        },
        relations={},
        values={},
    ),
    "auth_users": TableIndex(
        columns={
            "id": "uuid", "username": "text", "password_hash": "text", "ref_id": "uuid",
            "is_active": "bool", "created_at": "timestamp", "updated_at": "timestamp",
            "email": "text", "phone": "text", "email_verified_at": "timestamp",
            "phone_verified_at": "timestamp", "region": "text",
            "email_notify_activation_request": "bool", "email_notify_service_request": "bool",
        },
        relations={},
        values={},
    ),
    "bom_components": TableIndex(
        columns={
            "id": "uuid", "bom_id": "uuid", "component_type": "text", "component_id": "uuid",
            "qty": "number", "warehouse_id": "uuid",
        },
        relations={
            "bom_id": "boms", "warehouse_id": "warehouses",
        },
        values={
            "component_type": ("material", "product_item"),
        },
    ),
    "boms": TableIndex(
        columns={
            "id": "uuid", "product_id": "uuid", "version": "int", "created_at": "timestamp",
            "updated_at": "timestamp", "product_name": "text", "created_by": "uuid",
        },
        relations={
            "created_by": "auth_users", "product_id": "products",
        },
        values={},
    ),
    "business_fields": TableIndex(
        columns={
            "id": "uuid", "name": "text", "description": "text", "created_at": "timestamp",
            "updated_at": "timestamp", "label_vi": "text", "label_en": "text",
        },
        relations={},
        values={},
    ),
    "campaign_registrations": TableIndex(
        columns={
            "id": "uuid", "campaign_id": "uuid", "customer_id": "uuid", "note": "text",
            "created_at": "timestamp",
        },
        relations={
            "campaign_id": "campaigns", "customer_id": "customers",
        },
        values={},
    ),
    "campaign_visits": TableIndex(
        columns={
            "id": "uuid", "campaign_id": "uuid", "visited_at": "timestamp",
        },
        relations={
            "campaign_id": "campaigns",
        },
        values={},
    ),
    "campaigns": TableIndex(
        columns={
            "id": "uuid", "name": "text", "slug": "text", "product_id": "uuid",
            "business_field_id": "uuid", "organization_id": "uuid", "funnel_type": "text",
            "channel_type": "text", "status": "text", "sla_hours": "int", "created_by": "uuid",
            "assigned_person_id": "uuid", "start_at": "timestamp", "end_at": "timestamp",
            "created_at": "timestamp", "updated_at": "timestamp", "deleted_at": "timestamp",
            "note": "text",
        },
        relations={
            "assigned_person_id": "auth_users", "business_field_id": "business_fields",
            "created_by": "auth_users", "organization_id": "organizations",
            "product_id": "products",
        },
        values={
            "funnel_type": ("sales", "course"), "status": ("active", "ended"),
        },
    ),
    "chat_conversations": TableIndex(
        columns={
            "id": "uuid", "kind": "text", "direct_key": "text", "name": "text",
            "created_by": "uuid", "created_at": "timestamp", "last_message_at": "timestamp",
            "owner_id": "uuid",
        },
        relations={
            "created_by": "auth_users", "owner_id": "auth_users",
        },
        values={
            "kind": ("direct", "group"),
        },
    ),
    "chat_messages": TableIndex(
        columns={
            "id": "uuid", "conversation_id": "uuid", "sender_id": "uuid", "body": "text",
            "reply_to_id": "uuid", "recalled_at": "timestamp", "pinned_at": "timestamp",
            "pinned_by": "uuid", "created_at": "timestamp", "forwarded": "bool", "kind": "text",
        },
        relations={
            "conversation_id": "chat_conversations", "pinned_by": "auth_users",
            "reply_to_id": "chat_messages", "sender_id": "auth_users",
        },
        values={
            "kind": ("text", "system"),
        },
    ),
    "chat_participants": TableIndex(
        columns={
            "conversation_id": "uuid", "user_id": "uuid", "joined_at": "timestamp",
            "last_read_at": "timestamp", "cleared_at": "timestamp", "pinned_at": "timestamp",
            "muted": "bool", "archived_at": "timestamp", "can_add": "bool",
        },
        relations={
            "conversation_id": "chat_conversations", "user_id": "auth_users",
        },
        values={},
    ),
    "company_doc_node_products": TableIndex(
        columns={
            "node_id": "uuid", "product_id": "uuid",
        },
        relations={
            "node_id": "company_doc_nodes", "product_id": "products",
        },
        values={},
    ),
    "company_doc_node_versions": TableIndex(
        columns={
            "id": "uuid", "node_id": "uuid", "version": "int", "name": "text",
            "description": "text", "file_url": "text", "document_type": "text", "language": "text",
            "created_by_name": "text", "created_at": "timestamp",
        },
        relations={
            "node_id": "company_doc_nodes",
        },
        values={},
    ),
    "company_doc_nodes": TableIndex(
        columns={
            "id": "uuid", "parent_id": "uuid", "node_type": "text", "name": "text",
            "description": "text", "file_url": "text", "sort_order": "int", "created_by": "uuid",
            "created_at": "timestamp", "updated_at": "timestamp", "manualhub_product_id": "uuid",
            "manualhub_document_id": "uuid", "manualhub_document_type": "text",
            "manualhub_language": "text", "status": "text", "rejection_reason": "text",
            "pre_delete_status": "text", "version": "text", "language": "text",
            "document_type": "text", "pdf_cache_file_id": "uuid", "pdf_cache_source": "text",
            "root_id": "uuid", "document_group_id": "uuid", "is_current": "bool",
            "lineage_version": "text", "connection_types": "text[]",
        },
        relations={
            "created_by": "auth_users", "manualhub_document_id": "manualhub_documents",
            "manualhub_product_id": "products", "parent_id": "company_doc_nodes",
            "pdf_cache_file_id": "files", "root_id": "company_doc_nodes",
        },
        values={
            "language": ("vi", "en"), "node_type": ("folder", "document"),
            "status": ("draft", "review", "released", "rejected", "hidden", "pending_delete"),
        },
    ),
    "contact_messages": TableIndex(
        columns={
            "id": "uuid", "customer_id": "uuid", "name": "text", "phone": "text", "email": "text",
            "business_field": "text", "services": "text", "message": "text",
            "created_at": "timestamp", "read_at": "timestamp",
        },
        relations={
            "customer_id": "customers",
        },
        values={},
    ),
    "customer_business_fields": TableIndex(
        columns={
            "customer_id": "uuid", "business_field_id": "uuid",
        },
        relations={
            "business_field_id": "business_fields", "customer_id": "customers",
        },
        values={},
    ),
    "customer_customer_groups": TableIndex(
        columns={
            "customer_id": "uuid", "customer_group_id": "uuid",
        },
        relations={
            "customer_group_id": "customer_groups", "customer_id": "customers",
        },
        values={},
    ),
    "customer_groups": TableIndex(
        columns={
            "id": "uuid", "name": "text", "description": "text", "created_at": "timestamp",
            "updated_at": "timestamp", "label_vi": "text", "label_en": "text",
        },
        relations={},
        values={},
    ),
    "customer_logs": TableIndex(
        columns={
            "id": "uuid", "customer_id": "uuid", "actor_id": "uuid", "action": "text",
            "target_type": "text", "target_id": "uuid", "changes": "json",
            "created_at": "timestamp",
        },
        relations={
            "actor_id": "auth_users", "customer_id": "customers",
        },
        values={},
    ),
    "customer_new_interactions": TableIndex(
        columns={
            "customer_id": "uuid", "created_at": "timestamp",
        },
        relations={
            "customer_id": "customers",
        },
        values={},
    ),
    "customer_status_groups": TableIndex(
        columns={
            "id": "uuid", "name": "text", "label_vi": "text", "label_en": "text", "stage": "text",
            "sort_order": "int", "created_at": "timestamp", "updated_at": "timestamp",
        },
        relations={},
        values={
            "stage": ("lead", "student", "official", "lost", "spam"),
        },
    ),
    "customer_statuses": TableIndex(
        columns={
            "id": "uuid", "name": "text", "description": "text", "created_at": "timestamp",
            "updated_at": "timestamp", "label_vi": "text", "label_en": "text", "group": "text",
            "status_group_id": "uuid",
        },
        relations={
            "status_group_id": "customer_status_groups",
        },
        values={},
    ),
    "customer_team_members": TableIndex(
        columns={
            "id": "uuid", "customer_id": "uuid", "auth_user_id": "uuid", "full_name": "text",
            "phone": "text", "created_by": "uuid", "created_at": "timestamp",
        },
        relations={
            "auth_user_id": "auth_users", "created_by": "auth_users", "customer_id": "customers",
        },
        values={},
    ),
    "customer_views": TableIndex(
        columns={
            "id": "uuid", "customer_id": "uuid", "sales_id": "uuid", "viewed_at": "timestamp",
        },
        relations={
            "customer_id": "customers", "sales_id": "auth_users",
        },
        values={},
    ),
    "customers": TableIndex(
        columns={
            "id": "uuid", "code": "text", "full_name": "text", "email": "text", "phone": "text",
            "company_name": "text", "source": "text", "assigned_sales_id": "uuid",
            "organization_id": "uuid", "created_at": "timestamp", "updated_at": "timestamp",
            "deleted_at": "timestamp", "created_by": "uuid", "main_phone": "text",
            "website": "text", "status_id": "uuid", "address": "text", "main_email": "text",
            "last_contact_at": "timestamp", "gender": "text", "region": "text",
            "merged_into_id": "uuid", "customer_type": "text", "source_campaign_id": "uuid",
            "notes": "text", "self_of_organization_id": "uuid", "assigned_at": "timestamp",
            "last_inbound_at": "timestamp",
        },
        relations={
            "assigned_sales_id": "auth_users", "merged_into_id": "customers",
            "organization_id": "organizations", "self_of_organization_id": "organizations",
            "source_campaign_id": "campaigns", "created_by": "auth_users",
            "status_id": "customer_statuses",
        },
        values={
            "customer_type": ("lead", "student", "official", "spam", "lost"),
            "gender": ("male", "female"),
        },
    ),
    "file_links": TableIndex(
        columns={
            "id": "uuid", "file_id": "uuid", "entity_type": "text", "entity_id": "uuid",
            "purpose": "text", "display_order": "int", "created_at": "timestamp",
        },
        relations={
            "file_id": "files",
        },
        values={},
    ),
    "files": TableIndex(
        columns={
            "id": "uuid", "original_name": "text", "storage_key": "text", "mime_type": "text",
            "size_bytes": "int", "visibility": "text", "uploaded_by": "uuid",
            "created_at": "timestamp", "deleted_at": "timestamp",
        },
        relations={
            "uploaded_by": "auth_users",
        },
        values={
            "visibility": ("internal", "customer_visible"),
        },
    ),
    "finished_goods_receipt_items": TableIndex(
        columns={
            "id": "uuid", "finished_goods_receipt_id": "uuid", "product_item_id": "uuid",
        },
        relations={
            "finished_goods_receipt_id": "finished_goods_receipts",
        },
        values={},
    ),
    "finished_goods_receipts": TableIndex(
        columns={
            "id": "uuid", "work_order_id": "uuid", "qty": "number", "created_by": "uuid",
            "created_at": "timestamp", "qty_scrap": "number", "is_final": "bool",
        },
        relations={
            "created_by": "auth_users", "work_order_id": "manufacturing_work_orders",
        },
        values={},
    ),
    "goods_issue_items": TableIndex(
        columns={
            "id": "uuid", "goods_issue_id": "uuid", "material_id": "uuid", "serial_lot_id": "uuid",
            "qty": "number", "reason": "text",
        },
        relations={
            "goods_issue_id": "goods_issues", "material_id": "materials",
            "serial_lot_id": "material_serial_lots",
        },
        values={},
    ),
    "goods_issues": TableIndex(
        columns={
            "id": "uuid", "warehouse_id": "uuid", "source_type": "text", "source_id": "uuid",
            "customer_id": "uuid", "status": "text", "created_by": "uuid",
            "created_at": "timestamp", "updated_at": "timestamp", "decided_by": "uuid",
            "decided_at": "timestamp", "code": "text",
        },
        relations={
            "created_by": "auth_users", "customer_id": "customers", "decided_by": "auth_users",
            "warehouse_id": "warehouses",
        },
        values={
            "source_type": ("material_request", "work_order", "manual"),
            "status": ("draft", "completed", "cancelled"),
        },
    ),
    "goods_receipt_items": TableIndex(
        columns={
            "id": "uuid", "goods_receipt_id": "uuid", "material_id": "uuid",
            "qty_received": "number", "price": "number", "serial_lot_code": "text",
            "supplier_id": "uuid",
        },
        relations={
            "goods_receipt_id": "goods_receipts", "material_id": "materials",
            "supplier_id": "suppliers",
        },
        values={},
    ),
    "goods_receipts": TableIndex(
        columns={
            "id": "uuid", "warehouse_id": "uuid", "delivery_note_ref": "text", "status": "text",
            "created_by": "uuid", "created_at": "timestamp", "updated_at": "timestamp",
            "decided_by": "uuid", "decided_at": "timestamp", "code": "text",
        },
        relations={
            "created_by": "auth_users", "decided_by": "auth_users", "warehouse_id": "warehouses",
        },
        values={
            "status": ("draft", "completed", "cancelled"),
        },
    ),
    "goods_return_items": TableIndex(
        columns={
            "id": "uuid", "return_id": "uuid", "material_id": "uuid", "qty": "number",
            "reason": "text",
        },
        relations={
            "material_id": "materials", "return_id": "goods_returns",
        },
        values={},
    ),
    "goods_returns": TableIndex(
        columns={
            "id": "uuid", "po_id": "uuid", "goods_receipt_id": "uuid", "warehouse_id": "uuid",
            "status": "text", "created_by": "uuid", "created_at": "timestamp",
            "updated_at": "timestamp",
        },
        relations={
            "created_by": "auth_users", "po_id": "purchase_orders", "warehouse_id": "warehouses",
        },
        values={
            "status": ("pending", "sent_to_supplier", "resolved"),
        },
    ),
    "iot_devices": TableIndex(
        columns={
            "id": "uuid", "device_id": "text", "user_id": "uuid", "created_at": "timestamp",
            "mac": "text", "firmware_version": "text", "secret_hash": "text",
        },
        relations={
            "user_id": "auth_users",
        },
        values={},
    ),
    "iot_firmware_updates": TableIndex(
        columns={
            "id": "uuid", "device_id": "text", "firmware_id": "uuid", "version": "text",
            "from_version": "text", "created_at": "timestamp", "pushed_at": "timestamp",
            "confirmed_at": "timestamp", "closed_at": "timestamp",
        },
        relations={
            "device_id": "iot_devices", "firmware_id": "iot_firmwares",
        },
        values={},
    ),
    "iot_firmwares": TableIndex(
        columns={
            "id": "uuid", "version": "text", "sha256": "text", "size": "int",
            "created_at": "timestamp", "notes": "text", "filename": "text", "enabled": "bool",
        },
        relations={},
        values={},
    ),
    "issue_reports": TableIndex(
        columns={
            "id": "uuid", "product_item_id": "uuid", "reporter_id": "uuid", "category": "text",
            "alarm_code": "text", "description": "text", "status": "text", "reviewed_by": "uuid",
            "reviewed_at": "timestamp", "converted_case_id": "uuid", "created_at": "timestamp",
            "updated_at": "timestamp", "severity": "text",
        },
        relations={
            "converted_case_id": "support_cases", "product_item_id": "product_items",
            "reporter_id": "auth_users", "reviewed_by": "auth_users",
        },
        values={
            "severity": ("normal", "urgent"),
        },
    ),
    "keygen_history": TableIndex(
        columns={
            "id": "uuid", "key_type": "text", "input_data": "json", "output_data": "json",
            "generated_by": "uuid", "organization_id": "uuid", "created_at": "timestamp",
            "product_item_id": "uuid",
        },
        relations={
            "generated_by": "auth_users", "organization_id": "organizations",
            "product_item_id": "product_items",
        },
        values={},
    ),
    "leads": TableIndex(
        columns={
            "id": "uuid", "name": "text", "phone": "text", "email": "text", "services": "json",
            "created_at": "timestamp", "updated_at": "timestamp", "deleted_at": "timestamp",
            "business_field": "text", "notes": "text", "source_campaign_id": "uuid",
        },
        relations={
            "source_campaign_id": "campaigns",
        },
        values={},
    ),
    "lock_requests": TableIndex(
        columns={
            "id": "uuid", "product_item_id": "uuid", "requester_id": "uuid", "status": "text",
            "reason": "text", "approved_by": "uuid", "unlock_key": "text", "reject_reason": "text",
            "created_at": "timestamp", "resolved_at": "timestamp", "device_input": "text",
        },
        relations={
            "approved_by": "auth_users", "product_item_id": "product_items",
            "requester_id": "auth_users",
        },
        values={},
    ),
    "manualhub_activities": TableIndex(
        columns={
            "id": "uuid", "document_id": "uuid", "actor_id": "uuid", "actor_name": "text",
            "action": "text", "content": "text", "created_at": "timestamp",
        },
        relations={
            "document_id": "manualhub_documents",
        },
        values={},
    ),
    "manualhub_document_versions": TableIndex(
        columns={
            "id": "uuid", "document_id": "uuid", "version": "text", "title": "text",
            "content": "json", "file_url": "text", "created_by_name": "text",
            "created_at": "timestamp", "format": "text",
        },
        relations={
            "document_id": "manualhub_documents",
        },
        values={},
    ),
    "manualhub_documents": TableIndex(
        columns={
            "id": "uuid", "parent_id": "uuid", "product_id": "uuid", "title": "text",
            "description": "text", "document_type": "text", "format": "text", "content": "json",
            "status": "text", "language": "text", "version": "text", "author_id": "uuid",
            "author_name": "text", "is_current": "bool", "file_count": "int",
            "submitted_at": "timestamp", "released_at": "timestamp", "rejection_reason": "text",
            "created_at": "timestamp", "updated_at": "timestamp", "root_id": "uuid",
            "document_group_id": "uuid", "submitted_by_id": "uuid", "submitted_by_name": "text",
            "connection_types": "text[]",
        },
        relations={
            "parent_id": "manualhub_documents", "product_id": "products",
            "root_id": "manualhub_documents",
        },
        values={},
    ),
    "manufacturing_work_orders": TableIndex(
        columns={
            "id": "uuid", "type": "text", "output_type": "text", "product_id": "uuid",
            "product_item_id": "uuid", "bom_id": "uuid", "qty": "number", "project_id": "uuid",
            "task_id": "uuid", "status": "text", "created_by": "uuid", "created_at": "timestamp",
            "updated_at": "timestamp", "product_name": "text", "description": "text",
            "start_date": "date", "due_date": "date",
        },
        relations={
            "bom_id": "boms", "created_by": "auth_users", "product_id": "products",
            "project_id": "projects", "task_id": "tasks",
        },
        values={
            "output_type": ("product_item", "project_asset", "none"),
            "status": ("planned", "in_progress", "qc", "done", "cancelled"),
            "type": ("production", "repair"),
        },
    ),
    "material_consumptions": TableIndex(
        columns={
            "id": "uuid", "work_order_id": "uuid", "material_id": "uuid", "qty_actual": "number",
            "serial_lot_id": "uuid", "created_at": "timestamp",
        },
        relations={
            "material_id": "materials", "work_order_id": "manufacturing_work_orders",
        },
        values={},
    ),
    "material_serial_lot_consumptions": TableIndex(
        columns={
            "id": "uuid", "output_type": "text", "output_id": "uuid", "serial_lot_id": "uuid",
            "work_order_id": "uuid", "created_at": "timestamp",
        },
        relations={
            "work_order_id": "manufacturing_work_orders",
        },
        values={
            "output_type": ("product_item", "project_asset"),
        },
    ),
    "material_serial_lots": TableIndex(
        columns={
            "id": "uuid", "material_id": "uuid", "warehouse_id": "uuid", "code": "text",
            "label_code": "text", "qty": "number", "status": "text", "created_at": "timestamp",
            "updated_at": "timestamp",
        },
        relations={
            "material_id": "materials", "warehouse_id": "warehouses",
        },
        values={
            "status": ("in_stock", "consumed"),
        },
    ),
    "material_suppliers": TableIndex(
        columns={
            "material_id": "uuid", "supplier_id": "uuid", "is_primary": "bool",
            "created_at": "timestamp",
        },
        relations={
            "material_id": "materials", "supplier_id": "suppliers",
        },
        values={},
    ),
    "materials": TableIndex(
        columns={
            "id": "uuid", "sku": "text", "name": "text", "unit": "text", "tracking_type": "text",
            "reorder_point": "number", "created_at": "timestamp", "updated_at": "timestamp",
            "description": "text", "location": "text",
        },
        relations={},
        values={
            "tracking_type": ("none", "lot", "serial"),
        },
    ),
    "notification_delivery_log": TableIndex(
        columns={
            "id": "uuid", "user_id": "uuid", "channel": "text", "provider": "text",
            "recipient": "text", "template": "text", "status": "text", "error": "text",
            "provider_message_id": "text", "created_at": "timestamp", "sent_at": "timestamp",
        },
        relations={
            "user_id": "auth_users",
        },
        values={
            "channel": ("email", "zalo", "whatsapp"), "status": ("sent", "failed"),
        },
    ),
    "notifications": TableIndex(
        columns={
            "id": "uuid", "user_id": "uuid", "type": "text", "params": "json", "link": "text",
            "data": "json", "read_at": "timestamp", "created_at": "timestamp",
            "device_acked_at": "timestamp", "device_acked_by": "text",
            "device_pushed_at": "timestamp", "device_dismissed_at": "timestamp",
        },
        relations={
            "user_id": "auth_users",
        },
        values={},
    ),
    "organizations": TableIndex(
        columns={
            "id": "uuid", "code": "text", "name": "text", "parent_id": "uuid", "path": "text",
            "level": "int", "status": "text", "created_at": "timestamp", "updated_at": "timestamp",
            "agent_type": "text", "created_by": "uuid",
        },
        relations={
            "created_by": "auth_users", "parent_id": "organizations",
        },
        values={
            "agent_type": ("managing", "support"),
        },
    ),
    "password_reset_tokens": TableIndex(
        columns={
            "id": "uuid", "user_id": "uuid", "token_hash": "text", "expires_at": "timestamp",
            "used_at": "timestamp", "created_at": "timestamp",
        },
        relations={
            "user_id": "auth_users",
        },
        values={},
    ),
    "permissions": TableIndex(
        columns={
            "id": "uuid", "code": "text", "description": "text",
        },
        relations={},
        values={},
    ),
    "phases": TableIndex(
        columns={
            "id": "uuid", "project_id": "uuid", "name": "text", "phase_order": "int",
            "status": "text", "created_at": "timestamp", "updated_at": "timestamp",
        },
        relations={
            "project_id": "projects",
        },
        values={
            "status": ("todo", "in_progress", "done", "cancelled"),
        },
    ),
    "po_backorders": TableIndex(
        columns={
            "id": "uuid", "po_id": "uuid", "material_id": "uuid", "qty_outstanding": "number",
            "status": "text", "created_at": "timestamp", "updated_at": "timestamp",
        },
        relations={
            "material_id": "materials", "po_id": "purchase_orders",
        },
        values={
            "status": ("open", "closed", "cancelled"),
        },
    ),
    "po_goods_receipts": TableIndex(
        columns={
            "id": "uuid", "po_id": "uuid", "goods_receipt_id": "uuid", "created_at": "timestamp",
        },
        relations={
            "po_id": "purchase_orders",
        },
        values={},
    ),
    "product_agents": TableIndex(
        columns={
            "id": "uuid", "product_item_id": "uuid", "agent_organization_id": "uuid",
            "agent_role": "text", "created_by": "uuid", "created_at": "timestamp",
            "deleted_at": "timestamp",
        },
        relations={
            "agent_organization_id": "organizations", "created_by": "auth_users",
            "product_item_id": "product_items",
        },
        values={},
    ),
    "product_item_activation_requests": TableIndex(
        columns={
            "id": "uuid", "sales_user_id": "uuid", "customer_id": "uuid",
            "organization_id": "uuid", "inputs": "json", "status": "text", "result": "json",
            "reject_reason": "text", "submitted_at": "timestamp", "reviewed_by": "uuid",
            "reviewed_at": "timestamp", "created_at": "timestamp", "updated_at": "timestamp",
            "request_type": "text", "warranty_expiry": "timestamp",
        },
        relations={
            "customer_id": "customers", "organization_id": "organizations",
            "reviewed_by": "auth_users", "sales_user_id": "auth_users",
        },
        values={
            "request_type": ("activation", "supplemental_product"),
            "status": ("pending", "approved", "rejected"),
        },
    ),
    "product_item_aliases": TableIndex(
        columns={
            "id": "uuid", "product_item_id": "uuid", "owner_customer_id": "uuid", "alias": "text",
            "created_at": "timestamp", "updated_at": "timestamp",
        },
        relations={
            "owner_customer_id": "customers", "product_item_id": "product_items",
        },
        values={},
    ),
    "product_item_logs": TableIndex(
        columns={
            "id": "uuid", "product_item_id": "uuid", "event_type": "text", "actor_id": "uuid",
            "actor_role": "text", "source": "text", "customer_id": "uuid", "metadata": "json",
            "occurred_at": "timestamp", "created_at": "timestamp",
        },
        relations={
            "actor_id": "auth_users", "customer_id": "customers",
            "product_item_id": "product_items",
        },
        values={},
    ),
    "product_item_recall_requests": TableIndex(
        columns={
            "id": "uuid", "product_item_id": "uuid", "customer_id": "uuid", "requested_by": "uuid",
            "return_to_qs": "bool", "notes": "text", "status": "text", "confirmed_by": "uuid",
            "confirmed_at": "timestamp", "cancelled_by": "uuid", "cancelled_at": "timestamp",
            "created_at": "timestamp",
        },
        relations={
            "product_item_id": "product_items",
        },
        values={},
    ),
    "product_item_return_requests": TableIndex(
        columns={
            "id": "uuid", "requested_by": "uuid", "organization_id": "uuid", "item_ids": "json",
            "notes": "text", "status": "text", "reject_reason": "text", "reviewed_by": "uuid",
            "reviewed_at": "timestamp", "created_at": "timestamp",
        },
        relations={
            "organization_id": "organizations", "requested_by": "auth_users",
            "reviewed_by": "auth_users",
        },
        values={
            "status": ("pending", "approved", "rejected"),
        },
    ),
    "product_items": TableIndex(
        columns={
            "id": "uuid", "code": "text", "product_id": "uuid", "customer_id": "uuid",
            "manufacturing_date": "date", "installation_date": "date", "warranty_expiry": "date",
            "status": "text", "activated_at": "timestamp", "activated_by": "uuid",
            "activation_notes": "text", "created_at": "timestamp", "updated_at": "timestamp",
            "deleted_at": "timestamp", "recalled_at": "timestamp", "recall_notes": "text",
            "refurbished_at": "timestamp", "refurbish_notes": "text",
            "warranty_notified_at": "timestamp", "device_input": "text", "deleted_reason": "text",
        },
        relations={
            "activated_by": "auth_users", "customer_id": "customers", "product_id": "products",
        },
        values={},
    ),
    "product_ownership_transfer_requests": TableIndex(
        columns={
            "id": "uuid", "product_item_id": "uuid", "from_customer_id": "uuid",
            "to_customer_id": "uuid", "reason": "text", "status": "text", "reject_reason": "text",
            "requested_by": "uuid", "reviewed_by": "uuid", "reviewed_at": "timestamp",
            "created_at": "timestamp",
        },
        relations={
            "from_customer_id": "customers", "product_item_id": "product_items",
            "requested_by": "auth_users", "reviewed_by": "auth_users",
            "to_customer_id": "customers",
        },
        values={
            "status": ("pending", "approved", "rejected"),
        },
    ),
    "product_ownerships": TableIndex(
        columns={
            "id": "uuid", "product_item_id": "uuid", "owner_customer_id": "uuid",
            "is_current": "bool", "transferred_from_ownership_id": "uuid", "created_by": "uuid",
            "created_at": "timestamp", "deleted_at": "timestamp",
        },
        relations={
            "created_by": "auth_users", "owner_customer_id": "customers",
            "product_item_id": "product_items",
            "transferred_from_ownership_id": "product_ownerships",
        },
        values={},
    ),
    "product_support_limits": TableIndex(
        columns={
            "product_id": "uuid", "max_support_minutes": "int", "max_messages": "int",
            "max_emails": "int", "created_at": "timestamp", "updated_at": "timestamp",
        },
        relations={
            "product_id": "products",
        },
        values={},
    ),
    "product_user_access": TableIndex(
        columns={
            "id": "uuid", "product_item_id": "uuid", "auth_user_id": "uuid", "access_role": "text",
            "invited_by": "uuid", "created_at": "timestamp", "deleted_at": "timestamp",
            "role_id": "uuid", "role_name": "text",
        },
        relations={
            "auth_user_id": "auth_users", "invited_by": "auth_users",
            "product_item_id": "product_items", "role_id": "roles",
        },
        values={},
    ),
    "products": TableIndex(
        columns={
            "id": "uuid", "code": "text", "name": "text", "model_number": "text",
            "specifications": "json", "warranty_months": "int", "created_at": "timestamp",
            "updated_at": "timestamp", "deleted_at": "timestamp", "category": "text",
        },
        relations={},
        values={
            "category": ("catalogue", "controller", "servo", "inverter", "software"),
        },
    ),
    "project_asset_components": TableIndex(
        columns={
            "id": "uuid", "project_asset_id": "uuid", "product_item_id": "uuid",
            "work_order_id": "uuid", "installed_at": "timestamp",
        },
        relations={
            "project_asset_id": "project_assets", "work_order_id": "manufacturing_work_orders",
        },
        values={},
    ),
    "project_assets": TableIndex(
        columns={
            "id": "uuid", "project_id": "uuid", "work_order_id": "uuid", "name": "text",
            "serial_no": "text", "status": "text", "customer_id": "uuid", "warranty_start": "date",
            "warranty_end": "date", "activated_at": "timestamp", "created_at": "timestamp",
            "updated_at": "timestamp",
        },
        relations={
            "customer_id": "customers", "project_id": "projects",
            "work_order_id": "manufacturing_work_orders",
        },
        values={
            "status": ("building", "qc_passed", "delivered", "installed", "under_warranty", "recalled", "retired"),
        },
    ),
    "project_members": TableIndex(
        columns={
            "id": "uuid", "project_id": "uuid", "user_id": "uuid", "added_at": "timestamp",
        },
        relations={
            "project_id": "projects", "user_id": "auth_users",
        },
        values={},
    ),
    "projects": TableIndex(
        columns={
            "id": "uuid", "code": "text", "name": "text", "project_type": "text", "status": "text",
            "customer_id": "uuid", "budget": "number", "owner_id": "uuid",
            "companydoc_node_id": "uuid", "created_at": "timestamp", "updated_at": "timestamp",
        },
        relations={
            "customer_id": "customers", "owner_id": "auth_users",
        },
        values={
            "project_type": ("rd", "project_build", "internal"),
            "status": ("active", "on_hold", "completed", "cancelled"),
        },
    ),
    "purchase_order_items": TableIndex(
        columns={
            "id": "uuid", "po_id": "uuid", "material_id": "uuid", "qty": "number",
            "price": "number",
        },
        relations={
            "material_id": "materials", "po_id": "purchase_orders",
        },
        values={},
    ),
    "purchase_orders": TableIndex(
        columns={
            "id": "uuid", "pr_id": "uuid", "supplier_id": "uuid", "status": "text",
            "created_by": "uuid", "created_at": "timestamp", "updated_at": "timestamp",
            "sent_at": "timestamp", "sent_via": "text", "expected_delivery_date": "date",
            "code": "text",
        },
        relations={
            "created_by": "auth_users", "pr_id": "purchase_requisitions",
            "supplier_id": "suppliers",
        },
        values={
            "sent_via": ("email", "zalo", "manual"),
            "status": ("draft", "sent", "partially_received", "closed", "cancelled"),
        },
    ),
    "purchase_requisition_items": TableIndex(
        columns={
            "id": "uuid", "pr_id": "uuid", "material_id": "uuid", "qty": "number",
            "approved_qty": "number",
        },
        relations={
            "material_id": "materials", "pr_id": "purchase_requisitions",
        },
        values={},
    ),
    "purchase_requisitions": TableIndex(
        columns={
            "id": "uuid", "source_type": "text", "source_id": "uuid", "requested_by": "uuid",
            "status": "text", "approved_by": "uuid", "rejected_reason": "text",
            "created_at": "timestamp", "updated_at": "timestamp", "deleted_at": "timestamp",
            "reason": "text", "code": "text",
        },
        relations={
            "approved_by": "auth_users", "requested_by": "auth_users",
        },
        values={
            "source_type": ("material_request", "manual"),
            "status": ("pending_approval", "approved", "rejected", "partially_converted", "converted", "closed"),
        },
    ),
    "push_device_tokens": TableIndex(
        columns={
            "id": "uuid", "user_id": "uuid", "token": "text", "platform": "text",
            "user_agent": "text", "created_at": "timestamp", "last_seen_at": "timestamp",
        },
        relations={
            "user_id": "auth_users",
        },
        values={},
    ),
    "qc_records": TableIndex(
        columns={
            "id": "uuid", "ref_type": "text", "ref_id": "uuid", "result": "text",
            "inspector": "uuid", "notes": "text", "created_at": "timestamp",
        },
        relations={
            "inspector": "auth_users",
        },
        values={
            "ref_type": ("goods_receipt", "work_order"), "result": ("pass", "fail"),
        },
    ),
    "rbac_audit_logs": TableIndex(
        columns={
            "id": "uuid", "action_type": "text", "performed_by": "uuid", "target_user_id": "uuid",
            "target_role_id": "uuid", "target_permission_id": "uuid",
            "target_organization_id": "uuid", "metadata": "json", "created_at": "timestamp",
        },
        relations={
            "performed_by": "auth_users", "target_organization_id": "organizations",
            "target_permission_id": "permissions", "target_role_id": "roles",
            "target_user_id": "auth_users",
        },
        values={},
    ),
    "request_comments": TableIndex(
        columns={
            "id": "uuid", "request_kind": "text", "request_id": "uuid", "author_id": "uuid",
            "body": "text", "created_at": "timestamp",
        },
        relations={
            "author_id": "auth_users",
        },
        values={
            "request_kind": ("activation", "return", "lock", "transfer"),
        },
    ),
    "role_permissions": TableIndex(
        columns={
            "role_id": "uuid", "permission_id": "uuid",
        },
        relations={
            "permission_id": "permissions", "role_id": "roles",
        },
        values={},
    ),
    "roles": TableIndex(
        columns={
            "id": "uuid", "code": "text", "name": "text", "data_scope": "text", "kind": "text",
            "organization_id": "uuid", "description": "text", "created_at": "timestamp",
            "owner_customer_id": "uuid",
        },
        relations={
            "organization_id": "organizations", "owner_customer_id": "customers",
        },
        values={
            "data_scope": ("SELF", "ORGANIZATION", "ORGANIZATION_AND_CHILDREN", "ALL"),
        },
    ),
    "roles_owner_scope_rollback": TableIndex(
        columns={
            "role_id": "uuid", "organization_id": "uuid",
        },
        relations={},
        values={},
    ),
    "sales_round_robin_state": TableIndex(
        columns={
            "id": "int", "last_assigned_sales_id": "uuid", "updated_at": "timestamp",
        },
        relations={
            "last_assigned_sales_id": "auth_users",
        },
        values={},
    ),
    "sales_users": TableIndex(
        columns={
            "id": "uuid", "code": "text", "full_name": "text", "email": "text", "phone": "text",
            "position": "text", "status": "text", "organization_id": "uuid",
            "created_at": "timestamp", "updated_at": "timestamp", "deleted_at": "timestamp",
        },
        relations={
            "organization_id": "organizations",
        },
        values={},
    ),
    "schema_migrations": TableIndex(
        columns={
            "version": "int", "dirty": "bool",
        },
        relations={},
        values={},
    ),
    "service_logs": TableIndex(
        columns={
            "id": "uuid", "product_item_id": "uuid", "work_order_id": "uuid",
            "service_date": "timestamp", "service_type": "text", "issue_description": "text",
            "action_taken": "text", "parts_replaced": "json", "technician_id": "uuid",
            "customer_notes": "text", "internal_notes": "text", "created_at": "timestamp",
            "updated_at": "timestamp", "source_comment_id": "uuid", "event_type": "text",
            "event_metadata": "json",
        },
        relations={
            "product_item_id": "product_items", "source_comment_id": "work_order_comments",
            "technician_id": "auth_users", "work_order_id": "work_orders",
        },
        values={},
    ),
    "sessions": TableIndex(
        columns={
            "id": "uuid", "user_id": "uuid", "refresh_token_hash": "text",
            "access_token_jti": "uuid", "device_info": "text", "ip_address": "text",
            "expires_at": "timestamp", "created_at": "timestamp", "revoked_at": "timestamp",
        },
        relations={
            "user_id": "auth_users",
        },
        values={},
    ),
    "sso_tickets": TableIndex(
        columns={
            "id": "uuid", "user_id": "uuid", "token_hash": "text", "expires_at": "timestamp",
            "used_at": "timestamp", "created_at": "timestamp",
        },
        relations={
            "user_id": "auth_users",
        },
        values={},
    ),
    "stock": TableIndex(
        columns={
            "id": "uuid", "material_id": "uuid", "warehouse_id": "uuid", "qty": "number",
            "unit_cost": "number", "created_at": "timestamp", "updated_at": "timestamp",
        },
        relations={
            "material_id": "materials", "warehouse_id": "warehouses",
        },
        values={},
    ),
    "stock_movements": TableIndex(
        columns={
            "id": "uuid", "type": "text", "material_id": "uuid", "warehouse_id": "uuid",
            "qty": "number", "serial_lot_id": "uuid", "source_type": "text", "source_id": "uuid",
            "reason": "text", "created_by": "uuid", "created_at": "timestamp",
            "related_warehouse_id": "uuid",
        },
        relations={
            "created_by": "auth_users", "material_id": "materials",
            "related_warehouse_id": "warehouses", "serial_lot_id": "material_serial_lots",
            "warehouse_id": "warehouses",
        },
        values={
            "source_type": ("goods_receipt", "goods_issue", "material_request", "work_order", "stocktake", "manual", "goods_return"),
            "type": ("in", "out", "transfer", "adjust"),
        },
    ),
    "stocktake_lines": TableIndex(
        columns={
            "id": "uuid", "stocktake_id": "uuid", "material_id": "uuid", "system_qty": "number",
            "actual_qty": "number",
        },
        relations={
            "material_id": "materials", "stocktake_id": "stocktakes",
        },
        values={},
    ),
    "stocktakes": TableIndex(
        columns={
            "id": "uuid", "warehouse_id": "uuid", "stocktake_date": "date", "status": "text",
            "created_by": "uuid", "created_at": "timestamp", "updated_at": "timestamp",
            "code": "text",
        },
        relations={
            "created_by": "auth_users", "warehouse_id": "warehouses",
        },
        values={
            "status": ("open", "completed"),
        },
    ),
    "students": TableIndex(
        columns={
            "id": "uuid", "full_name": "text", "email": "text", "phone": "text",
            "business_field": "text", "deposit_agreed": "bool", "status": "text", "notes": "text",
            "created_at": "timestamp", "updated_at": "timestamp", "deleted_at": "timestamp",
            "source_campaign_id": "uuid",
        },
        relations={
            "source_campaign_id": "campaigns",
        },
        values={},
    ),
    "suppliers": TableIndex(
        columns={
            "id": "uuid", "name": "text", "phone": "text", "email": "text", "address": "text",
            "payment_terms": "text", "rating": "number", "created_at": "timestamp",
            "updated_at": "timestamp",
        },
        relations={},
        values={},
    ),
    "support_appointments": TableIndex(
        columns={
            "id": "uuid", "case_id": "uuid", "product_item_id": "uuid", "customer_user_id": "uuid",
            "support_user_id": "uuid", "support_organization_id": "uuid",
            "start_at_utc": "timestamp", "end_at_utc": "timestamp", "customer_timezone": "text",
            "status": "text", "meeting_url": "text", "created_at": "timestamp",
            "updated_at": "timestamp", "reminder_sent_at": "timestamp",
            "start_notified_at": "timestamp",
        },
        relations={
            "case_id": "support_cases", "customer_user_id": "auth_users",
            "product_item_id": "product_items", "support_organization_id": "organizations",
            "support_user_id": "auth_users",
        },
        values={},
    ),
    "support_assignments": TableIndex(
        columns={
            "id": "uuid", "case_id": "uuid", "assigned_to": "uuid",
            "support_organization_id": "uuid", "is_current": "bool", "assigned_by": "uuid",
            "created_at": "timestamp", "accepted_at": "timestamp",
        },
        relations={
            "assigned_by": "auth_users", "assigned_to": "auth_users", "case_id": "support_cases",
            "support_organization_id": "organizations",
        },
        values={},
    ),
    "support_attachments": TableIndex(
        columns={
            "id": "uuid", "case_id": "uuid", "message_id": "uuid", "file_id": "uuid",
            "uploaded_by": "uuid", "created_at": "timestamp",
        },
        relations={
            "case_id": "support_cases", "message_id": "support_messages",
            "uploaded_by": "auth_users",
        },
        values={},
    ),
    "support_cancel_requests": TableIndex(
        columns={
            "id": "uuid", "case_id": "uuid", "requested_by": "uuid", "reason": "text",
            "status": "text", "reviewed_by": "uuid", "reviewed_at": "timestamp",
            "created_at": "timestamp", "updated_at": "timestamp", "kind": "text",
        },
        relations={
            "case_id": "support_cases", "requested_by": "auth_users", "reviewed_by": "auth_users",
        },
        values={},
    ),
    "support_case_events": TableIndex(
        columns={
            "id": "uuid", "case_id": "uuid", "event_type": "text", "old_value": "text",
            "new_value": "text", "actor_id": "uuid", "created_at": "timestamp",
        },
        relations={
            "actor_id": "auth_users", "case_id": "support_cases",
        },
        values={},
    ),
    "support_cases": TableIndex(
        columns={
            "id": "uuid", "case_number": "text", "product_item_id": "uuid",
            "customer_organization_id": "uuid", "created_by": "uuid", "category": "text",
            "priority": "text", "status": "text", "subject": "text", "description": "text",
            "first_response_at": "timestamp", "resolved_at": "timestamp", "closed_at": "timestamp",
            "document_id": "uuid", "document_version": "text", "created_at": "timestamp",
            "updated_at": "timestamp", "deleted_at": "timestamp", "period_started_at": "timestamp",
            "long_session_notified_at": "timestamp", "work_order_id": "uuid",
            "support_mode": "text", "customer_hidden_at": "timestamp",
            "session_ended_at": "timestamp", "session_started_at": "timestamp",
            "session_minutes_charged": "int", "session_exhausted_at": "timestamp",
            "overtime_due_at": "timestamp", "overtime_asked_at": "timestamp",
            "reject_reason": "text",
        },
        relations={
            "created_by": "auth_users", "customer_organization_id": "organizations",
            "product_item_id": "product_items", "work_order_id": "work_orders",
        },
        values={},
    ),
    "support_entitlement_transactions": TableIndex(
        columns={
            "id": "uuid", "entitlement_id": "uuid", "case_id": "uuid", "time_entry_id": "uuid",
            "type": "text", "delta_minutes": "int", "balance_after_minutes": "int",
            "description": "text", "created_by": "uuid", "created_at": "timestamp", "kind": "text",
            "delta_messages": "int", "balance_after_messages": "int",
        },
        relations={
            "case_id": "support_cases", "time_entry_id": "support_time_entries",
            "created_by": "auth_users", "entitlement_id": "support_entitlements",
        },
        values={},
    ),
    "support_entitlements": TableIndex(
        columns={
            "id": "uuid", "product_item_id": "uuid", "included_minutes": "int",
            "used_minutes": "int", "created_at": "timestamp", "updated_at": "timestamp",
            "low_balance_notified_at": "timestamp", "included_messages": "int",
            "used_messages": "int",
        },
        relations={
            "product_item_id": "product_items",
        },
        values={},
    ),
    "support_messages": TableIndex(
        columns={
            "id": "uuid", "case_id": "uuid", "sender_id": "uuid", "type": "text", "body": "text",
            "created_at": "timestamp", "translated_body": "text", "translated_lang": "text",
            "translated_at": "timestamp", "translated_source": "text", "reply_to_id": "uuid",
            "recalled_at": "timestamp", "recalled_by": "uuid",
        },
        relations={
            "case_id": "support_cases", "reply_to_id": "support_messages",
            "sender_id": "auth_users",
        },
        values={},
    ),
    "support_ratings": TableIndex(
        columns={
            "id": "uuid", "case_id": "uuid", "resolution": "text", "score": "int",
            "comment": "text", "created_by": "uuid", "created_at": "timestamp",
            "product_item_id": "uuid", "updated_at": "timestamp",
        },
        relations={
            "case_id": "support_cases", "created_by": "auth_users",
            "product_item_id": "product_items",
        },
        values={},
    ),
    "support_time_entries": TableIndex(
        columns={
            "id": "uuid", "case_id": "uuid", "appointment_id": "uuid", "source": "text",
            "duration_minutes": "int", "occurred_at": "timestamp", "created_by": "uuid",
            "created_at": "timestamp",
        },
        relations={
            "appointment_id": "support_appointments", "case_id": "support_cases",
            "created_by": "auth_users",
        },
        values={},
    ),
    "support_waiting_message_events": TableIndex(
        columns={
            "id": "uuid", "message_id": "uuid", "type": "text", "actor_id": "uuid",
            "target_id": "uuid", "created_at": "timestamp",
        },
        relations={
            "message_id": "support_waiting_messages",
        },
        values={},
    ),
    "support_waiting_message_helpers": TableIndex(
        columns={
            "message_id": "uuid", "user_id": "uuid", "added_by": "uuid", "created_at": "timestamp",
        },
        relations={
            "added_by": "auth_users", "message_id": "support_waiting_messages",
            "user_id": "auth_users",
        },
        values={},
    ),
    "support_waiting_message_replies": TableIndex(
        columns={
            "id": "uuid", "message_id": "uuid", "author_id": "uuid", "content": "text",
            "created_at": "timestamp", "reply_to_id": "uuid", "recalled_at": "timestamp",
            "recalled_by": "uuid",
        },
        relations={
            "message_id": "support_waiting_messages",
            "reply_to_id": "support_waiting_message_replies",
        },
        values={},
    ),
    "support_waiting_message_views": TableIndex(
        columns={
            "message_id": "uuid", "user_id": "uuid", "seen_at": "timestamp",
            "marked_unread": "bool",
        },
        relations={
            "message_id": "support_waiting_messages", "user_id": "auth_users",
        },
        values={},
    ),
    "support_waiting_messages": TableIndex(
        columns={
            "id": "uuid", "product_item_id": "uuid", "created_by": "uuid", "title": "text",
            "content": "text", "status": "text", "handled_by": "uuid", "handled_at": "timestamp",
            "created_at": "timestamp", "assigned_to": "uuid", "assigned_by": "uuid",
            "assigned_at": "timestamp", "escalated_at": "timestamp", "escalated_by": "uuid",
            "customer_seen_at": "timestamp", "customer_marked_unread": "bool",
            "staff_deleted_at": "timestamp", "customer_deleted_at": "timestamp",
            "customer_id": "uuid",
        },
        relations={
            "escalated_by": "auth_users", "product_item_id": "product_items",
        },
        values={},
    ),
    "tasks": TableIndex(
        columns={
            "id": "uuid", "project_id": "uuid", "phase_id": "uuid", "title": "text",
            "description": "text", "priority": "text", "due_date": "date", "status": "text",
            "parent_task_id": "uuid", "assignee_id": "uuid", "estimated_finish_date": "date",
            "source_type": "text", "source_id": "uuid", "created_at": "timestamp",
            "updated_at": "timestamp",
        },
        relations={
            "assignee_id": "auth_users", "parent_task_id": "tasks", "phase_id": "phases",
            "project_id": "projects",
        },
        values={
            "priority": ("low", "medium", "high", "urgent"),
            "source_type": ("support_case", "work_order"),
            "status": ("todo", "in_progress", "done", "cancelled"),
        },
    ),
    "user_organizations": TableIndex(
        columns={
            "user_id": "uuid", "organization_id": "uuid",
        },
        relations={
            "organization_id": "organizations", "user_id": "auth_users",
        },
        values={},
    ),
    "user_permissions": TableIndex(
        columns={
            "user_id": "uuid", "permission_id": "uuid", "granted_by": "uuid",
            "created_at": "timestamp",
        },
        relations={
            "granted_by": "auth_users", "permission_id": "permissions", "user_id": "auth_users",
        },
        values={},
    ),
    "user_profiles": TableIndex(
        columns={
            "id": "uuid", "user_id": "uuid", "first_name": "text", "last_name": "text",
            "avatar_url": "text", "created_at": "timestamp", "updated_at": "timestamp",
        },
        relations={
            "user_id": "auth_users",
        },
        values={},
    ),
    "user_roles": TableIndex(
        columns={
            "user_id": "uuid", "role_id": "uuid",
        },
        relations={
            "role_id": "roles", "user_id": "auth_users",
        },
        values={},
    ),
    "user_types": TableIndex(
        columns={
            "code": "text", "name": "text", "description": "text", "created_at": "timestamp",
        },
        relations={},
        values={},
    ),
    "verification_codes": TableIndex(
        columns={
            "id": "uuid", "auth_user_id": "uuid", "type": "text", "target": "text", "code": "text",
            "code_hash": "text", "purpose": "text", "expires_at": "timestamp",
            "verified_at": "timestamp", "attempts": "int", "created_at": "timestamp",
        },
        relations={
            "auth_user_id": "auth_users",
        },
        values={},
    ),
    "warehouses": TableIndex(
        columns={
            "id": "uuid", "name": "text", "created_at": "timestamp", "updated_at": "timestamp",
            "address": "text", "status": "text", "code": "text", "is_default": "bool",
        },
        relations={},
        values={
            "status": ("active", "paused", "closed"),
        },
    ),
    "wo_operations": TableIndex(
        columns={
            "id": "uuid", "work_order_id": "uuid", "step_name": "text", "step_order": "int",
            "assignee_id": "uuid", "status": "text", "created_at": "timestamp",
            "updated_at": "timestamp",
        },
        relations={
            "assignee_id": "auth_users", "work_order_id": "manufacturing_work_orders",
        },
        values={
            "status": ("todo", "in_progress", "done"),
        },
    ),
    "work_order_comments": TableIndex(
        columns={
            "id": "uuid", "work_order_id": "uuid", "author_id": "uuid", "content": "text",
            "is_internal": "bool", "created_at": "timestamp", "updated_at": "timestamp",
            "deleted_at": "timestamp",
        },
        relations={
            "author_id": "auth_users", "work_order_id": "work_orders",
        },
        values={},
    ),
    "work_orders": TableIndex(
        columns={
            "id": "uuid", "order_number": "text", "product_item_id": "uuid", "type": "text",
            "priority": "text", "assigned_to": "uuid", "description": "text", "status": "text",
            "scheduled_date": "date", "started_at": "timestamp", "completed_at": "timestamp",
            "created_by": "uuid", "created_at": "timestamp", "updated_at": "timestamp",
            "deleted_at": "timestamp",
        },
        relations={
            "assigned_to": "auth_users", "created_by": "auth_users",
            "product_item_id": "product_items",
        },
        values={},
    ),
}
