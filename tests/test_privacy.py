from core import engine
from core.jev_client import JevError
from core.privacy import redact_messages, redact_text


def test_redact_common_personal_data():
    text = redact_text(
        "手机 13800138000，座机 010-12345678，邮箱 a.b+tag@example.com，"
        "身份证 11010519491231002X，卡号 6222 0212 3456 7890。"
    )
    assert "13800138000" not in text and "[手机号]" in text
    assert "010-12345678" not in text and "[电话号码]" in text
    assert "a.b+tag@example.com" not in text and "[邮箱]" in text
    assert "11010519491231002X" not in text and "[身份证号]" in text
    assert "6222 0212 3456 7890" not in text and "[银行卡号]" in text


def test_group_names_are_mapped_consistently():
    messages, reply_to = redact_messages([
        ("her", "13800138000", "阿杰"),
        ("me", "收到"),
        {"from": "her", "text": "a@example.com", "name": "阿杰"},
    ], "阿杰")

    assert messages[0][2] == messages[2]["name"] == reply_to == "群成员A"
    assert "13800138000" not in messages[0][1]
    assert "a@example.com" not in messages[2]["text"]


def test_engine_redacts_before_calling_models(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "sk-test")
    seen = {}

    def no_jev(*args, **kwargs):
        raise JevError("no jev")

    def fake_judge(state, questions, spec, base_url, model, timeout, api_key=None):
        seen["state"] = state
        return {"answers": {}, "usage": {}}

    def fake_draft(messages, relationship, **kwargs):
        seen["messages"] = messages
        seen["relationship"] = relationship
        seen["reply_to"] = kwargs.get("reply_to")
        return ["收到"]

    monkeypatch.setattr(engine, "ask", no_jev)
    monkeypatch.setattr(engine, "_judge_llm", fake_judge)
    monkeypatch.setattr(engine, "draft_candidates", fake_draft)
    out = engine.analyze(
        [("her", "打我 13800138000", "阿杰")],
        "朋友 a@example.com",
        reply_to="阿杰",
        redact_sensitive=True,
    )

    assert "13800138000" not in str(seen["state"])
    assert "a@example.com" not in seen["relationship"]
    assert seen["messages"][0][1] == "打我 [手机号]"
    assert seen["messages"][0][2] == seen["reply_to"] == "群成员A"
    assert out["reply_to"] == "阿杰"
