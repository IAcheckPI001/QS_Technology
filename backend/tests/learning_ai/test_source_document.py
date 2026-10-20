from dataclasses import dataclass
from uuid import uuid4

from app.modules.learning_ai.extraction.validators import Role
from app.modules.learning_ai.ingestion.prefilter import SkipReason, is_trivial, prefilter
from app.modules.learning_ai.ingestion.source_document import build_source_document


@dataclass
class Row:
    user_message: str | None
    staff_message: str | None


def _doc(*rows: tuple[str | None, str | None]):
    return build_source_document(uuid4(), [Row(u, s) for u, s in rows])


def test_units_follow_turn_order_and_skip_empty_messages():
    doc = _doc(("F86 lệch xung", "Anh kiểm tra P01"), (None, "Đặt P01 = 10000"), ("   ", None), ("Được rồi", ""))

    assert [(u.locator, u.role, u.text) for u in doc.units] == [
        ("m1", Role.CUSTOMER, "F86 lệch xung"),
        ("m2", Role.STAFF, "Anh kiểm tra P01"),
        ("m3", Role.STAFF, "Đặt P01 = 10000"),
        ("m4", Role.CUSTOMER, "Được rồi"),
    ]
    assert doc.render_for_llm().splitlines()[0] == "[m1][customer] F86 lệch xung"


def test_source_id_is_stable_for_same_content_and_changes_with_content():
    session_id = uuid4()
    a = build_source_document(session_id, [Row("hỏi", "đáp")])
    b = build_source_document(session_id, [Row("hỏi", "đáp")])
    c = build_source_document(session_id, [Row("hỏi", "đáp khác")])

    assert a.source_id == b.source_id
    assert a.source_id != c.source_id


def test_source_view_maps_locators_to_roles():
    view = _doc(("hỏi", "đáp")).to_source_view()

    assert view.units == {"m1": Role.CUSTOMER, "m2": Role.STAFF}


def test_with_texts_keeps_identity():
    doc = _doc(("gọi 0912345678", "dạ"))
    redacted = doc.with_texts({"m1": "gọi [PHONE_1]"})

    assert redacted.units[0].text == "gọi [PHONE_1]"
    assert (redacted.source_id, redacted.content_hash) == (doc.source_id, doc.content_hash)


def test_greeting_mixed_with_question_is_not_trivial():
    assert not is_trivial("xin chào, tôi cần giới thiệu về F86")
    assert not is_trivial("xin chào nha, tôi biết ơn vì bạn đã tư vấn, vậy còn F54 thì sao?")
    assert not is_trivial("chào anh, cho em hỏi lỗi encoder")


def test_pure_greetings_are_trivial():
    assert is_trivial("xin chào")
    assert is_trivial("dạ ok cảm ơn anh nhiều ạ")
    assert is_trivial("Chúc anh một ngày tốt lành!")


def test_registry_code_makes_message_substantive():
    assert not is_trivial("modbus", frozenset({"modbus"}))


def test_prefilter_skips_greeting_only_conversation():
    assert prefilter(_doc(("xin chào", "dạ em chào anh"), ("cảm ơn em", "dạ"))) == SkipReason.GREETING_ONLY


def test_prefilter_requires_both_sides():
    assert prefilter(_doc(("F86 lệch xung mỗi vòng khi chạy tốc độ cao", None))) == SkipReason.NO_STAFF_MESSAGE
    assert prefilter(_doc((None, "Anh kiểm tra P01 giúp em"))) == SkipReason.NO_CUSTOMER_MESSAGE


def test_prefilter_skips_too_short_conversation():
    assert prefilter(_doc(("lỗi gì", "E01"))) == SkipReason.TOO_SHORT


def test_prefilter_keeps_greeting_with_real_question():
    doc = _doc(("xin chào, tôi cần giới thiệu về F86", "Dạ F86 là servo driver 400W hỗ trợ điều khiển xung"))

    assert prefilter(doc) is None
