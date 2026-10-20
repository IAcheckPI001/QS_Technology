import pytest

from app.modules.learning_ai.privacy.pii_patterns import find_regex_spans
from app.modules.learning_ai.privacy.schemas import FindingType as T


def _found(text: str) -> list[tuple[str, T]]:
    return [(text[s.start:s.end], s.type) for s in find_regex_spans(text)]


@pytest.mark.parametrize("text, expected", [
    ("email a.b@abc.com.vn nhé", ("a.b@abc.com.vn", T.EMAIL)),
    ("gọi 0912 345 678 giúp", ("0912 345 678", T.PHONE)),
    ("số +84912345678", ("+84912345678", T.PHONE)),
    ("cccd: 012345678901", ("012345678901", T.NATIONAL_ID)),
    ("mst 0312345678", ("0312345678", T.TAX_CODE)),
    ("stk 1903 1234 5678 9", ("1903 1234 5678 9", T.BANK_ACCOUNT)),
    ("IP 192.168.1.10", ("192.168.1.10", T.IP_ADDRESS)),
    ("giá 2.500.000đ", ("2.500.000đ", T.PRICE_AMOUNT)),
    ("giá 500k", ("500k", T.PRICE_AMOUNT)),
    ("500k nhé", ("500k", T.PRICE_AMOUNT)),
    ("500 ngàn", ("500 ngàn", T.PRICE_AMOUNT)),
    ("năm trăm ngàn thôi", ("năm trăm ngàn", T.PRICE_AMOUNT)),
    ("hai triệu rưỡi", ("hai triệu rưỡi", T.PRICE_AMOUNT)),
    ("1tr2 nhé", ("1tr2", T.PRICE_AMOUNT)),
    ("2 củ", ("2 củ", T.PRICE_AMOUNT)),
    ("$120", ("$120", T.PRICE_AMOUNT)),
    ("chiết khấu 10%", ("10%", T.DISCOUNT)),
])
def test_detects_structured_pii_and_prices(text, expected):
    assert _found(text) == [expected]


@pytest.mark.parametrize("text", [
    "P01 = 10000", "131072 xung", "10 nghìn xung", "F86", "24VDC", "5k ohm", "10kW",
    "firmware 2.1.10", "duty 50%", "ngày 20.10.2026", "5 lít dầu", "ba ngàn vòng/phút",
])
def test_technical_values_are_not_redacted(text):
    assert _found(text) == []
