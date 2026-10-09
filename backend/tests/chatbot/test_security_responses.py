from app.modules.chatbot.stages.security import get_response_message, normalize_locale


def test_response_locale_is_allowlisted_and_normalized():
    assert normalize_locale("vi-VN") == "vi"
    assert normalize_locale("en-US") == "en"
    assert normalize_locale("fr-FR") == "en"


def test_block_response_is_localized():
    assert "CNC" in get_response_message("request_blocked", "vi")
    assert "CNC" in get_response_message("request_blocked", "en")
