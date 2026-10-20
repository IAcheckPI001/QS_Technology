import asyncio
import json
from uuid import uuid4

import pytest

from app.modules.learning_ai.extraction.validators import Role
from app.modules.learning_ai.ingestion.service import IngestionStatus, LearningIngestionService
from app.modules.learning_ai.ingestion.source_document import SourceUnit, build_source_document
from app.modules.learning_ai.privacy.pipeline import PrivacyPipeline
from app.modules.learning_ai.privacy.schemas import FindingType, PrivacyCheckUnavailable, SensitivityFlag
from app.modules.learning_ai.privacy.sensitivity_checker import SensitivityChecker
from app.modules.learning_ai.privacy.windowing import build_windows
from tests.learning_ai.builders import FakeProvider, FakeRepository, Responder, Row, finding, reviewing, word_count


def _pipeline(responder: Responder, window_tokens: int = 1000) -> tuple[PrivacyPipeline, FakeProvider]:
    provider = FakeProvider(responder)
    return PrivacyPipeline(SensitivityChecker(provider, window_tokens=window_tokens,
                                              token_counter=word_count)), provider


def _doc(*rows: tuple[str | None, str | None]):
    return build_source_document(uuid4(), [Row(u, s) for u, s in rows])


def _texts(result) -> list[str]:
    return [u.text for u in result.document.units]


def test_redacts_regex_and_model_findings_with_stable_placeholders():
    doc = _doc(("Em là Minh bên Công ty ABC, sđt 0912345678", "Dạ anh Minh, giá bộ F86 là 500 ngàn, bảo hành 24 tháng"),
               ("minh cần lắp ở xưởng 2", "Dạ"))
    pipeline, _ = _pipeline(reviewing(
        finding("m1", "pii", "person_name", "Minh"),
        finding("m1", "pii", "organization", "Công ty ABC"),
        finding("m2", "policy", "warranty", "bảo hành 24 tháng"),
        finding("m3", "customer_specific", "site_config", "xưởng 2"),
    ))

    result = asyncio.run(pipeline.run(doc))

    assert _texts(result) == [
        "Em là [PERSON_1] bên [ORG_1], sđt [PHONE_1]",
        "Dạ anh [PERSON_1], giá bộ F86 là [PRICE_1], bảo hành 24 tháng",
        "[PERSON_1] cần lắp ở xưởng 2",
        "Dạ",
    ]
    assert result.pii_types_detected == [FindingType.ORGANIZATION, FindingType.PERSON_NAME, FindingType.PHONE]
    assert result.flags_by_locator == {
        "m2": [SensitivityFlag.POLICY_COMMITMENT, SensitivityFlag.PRICING],
        "m3": [SensitivityFlag.CUSTOMER_SPECIFIC],
    }
    assert result.redaction_applied and result.checker_model == "fake-ollama"
    assert result.unverified_findings == 0 and result.residual_redactions == 0


def test_model_receives_regex_redacted_text_only():
    pipeline, provider = _pipeline(reviewing())

    asyncio.run(pipeline.run(_doc(("sđt 0912345678 nhé", "giá 2 củ"))))

    sent = json.dumps(provider.calls, ensure_ascii=False)
    assert "0912345678" not in sent and "2 củ" not in sent
    assert "[PHONE_1]" in sent and "[PRICE_1]" in sent


def test_hallucinated_or_out_of_window_findings_are_dropped():
    def respond(payload):
        locators = [t["locator"] for t in payload["targets"]]
        return {"reviewed_locators": locators, "findings": [
            finding("m1", "pii", "person_name", "Hùng"),          # không có trong text
            finding("m9", "pii", "person_name", "Lan"),           # locator ngoài cửa sổ
        ]}
    pipeline, _ = _pipeline(respond)

    result = asyncio.run(pipeline.run(_doc(("F86 lệch xung", "kiểm tra P01"))))

    assert result.unverified_findings == 2
    assert _texts(result) == ["F86 lệch xung", "kiểm tra P01"]


def test_entity_found_in_early_window_is_redacted_in_later_windows():
    rows = [("Em là Minh, máy F86 báo lỗi E01 khi chạy", "Dạ anh kiểm tra nguồn cấp")] + \
           [("Vẫn lỗi E01 sau khi kiểm tra nguồn", "Anh đo điện áp chân CN1")] * 3 + \
           [("Minh đo rồi, điện áp ổn định", "Dạ vậy anh thay cáp encoder")]
    doc = _doc(*rows)

    def respond(payload):   # model chỉ nhận ra "Minh" ở cửa sổ đầu tiên
        locators = [t["locator"] for t in payload["targets"]]
        found = [finding("m1", "pii", "person_name", "Minh")] if "m1" in locators else []
        return {"reviewed_locators": locators, "findings": found}
    pipeline, provider = _pipeline(respond, window_tokens=40)

    result = asyncio.run(pipeline.run(doc))

    assert len(provider.calls) > 1
    assert provider.calls[-1]["known_entities"] == ["Minh"]
    assert all("Minh" not in t for t in _texts(result))


@pytest.mark.parametrize("responder", [
    lambda p: (_ for _ in ()).throw(TimeoutError()),                            # provider lỗi
    lambda p: {"findings": []},                                                 # sai schema
    lambda p: {"reviewed_locators": [], "findings": []},                        # không đọc hết
    lambda p: {"reviewed_locators": [t["locator"] for t in p["targets"]],
               "findings": [{"locator": "m1", "category": "secret", "type": "x", "text": "ab"}]},
])
def test_fail_closed_when_check_is_incomplete(responder):
    pipeline, _ = _pipeline(responder)

    with pytest.raises(PrivacyCheckUnavailable):
        asyncio.run(pipeline.run(_doc(("F86 lệch xung", "kiểm tra P01"))))


def test_windows_keep_messages_whole_and_add_context():
    units = [SourceUnit(locator=f"m{i}", role=Role.CUSTOMER, text="một hai ba bốn năm") for i in range(1, 6)]

    windows = build_windows(units, budget_tokens=20, count_tokens=word_count)

    assert [[u.locator for u in w.targets] for w in windows] == [["m1", "m2"], ["m3", "m4"], ["m5"]]
    assert [u.locator for u in windows[1].context] == ["m1", "m2"]


def test_oversized_message_is_split_into_verbatim_pieces():
    text = "Câu một dài. " * 10 + "Câu cuối."
    unit = SourceUnit(locator="m1", role=Role.STAFF, text=text)

    windows = build_windows([unit], budget_tokens=12, count_tokens=word_count)

    pieces = [u for w in windows for u in w.targets]
    assert len(pieces) > 1
    assert all(p.locator == "m1" and p.text in text for p in pieces)


def test_service_skips_without_calling_model():
    pipeline, provider = _pipeline(reviewing())
    service = LearningIngestionService(FakeRepository([Row("xin chào", "dạ em chào anh")]), pipeline)

    result = asyncio.run(service.prepare(uuid4()))

    assert result.status == IngestionStatus.SKIPPED
    assert result.reason == "greeting_only"
    assert provider.calls == []


def test_service_reports_privacy_unavailable():
    pipeline, _ = _pipeline(lambda p: (_ for _ in ()).throw(ConnectionError()))
    rows = [Row("xin chào, tôi cần giới thiệu về F86", "Dạ F86 là servo driver 400W điều khiển xung")]

    result = asyncio.run(LearningIngestionService(FakeRepository(rows), pipeline).prepare(uuid4()))

    assert result.status == IngestionStatus.PRIVACY_UNAVAILABLE
    assert result.privacy is None


def test_service_returns_redacted_document():
    pipeline, _ = _pipeline(reviewing())
    rows = [Row("F86 lệch xung, gọi em 0912345678", "Dạ anh kiểm tra P01 giúp em nhé")]

    result = asyncio.run(LearningIngestionService(FakeRepository(rows), pipeline).prepare(uuid4()))

    assert result.status == IngestionStatus.READY
    assert result.privacy.document.units[0].text == "F86 lệch xung, gọi em [PHONE_1]"
