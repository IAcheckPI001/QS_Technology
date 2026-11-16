"""Truy vấn thô CRM Reporting API (tool `crm_schema`, `crm_query`): LLM tự chọn bảng/cột/join.

LLM dựng query theo contract của CRM; dịch vụ AI chỉ kiểm tra hình dạng query, chặn bảng/cột bí
mật (`policy.py`) và đổi preset ngày thành ngày cụ thể. Quyết định 2026-11-10 (phương án C, D-005);
catalog cố định (phương án A) đã bỏ 2026-11-16 (D-010).
"""
