from types import SimpleNamespace

import anthropic

from core import llm


def test_anthropic_chat_uses_real_sdk_signature(monkeypatch):
    seen = {}

    def fake_post(self, path, *, body, options, cast_to, stream, stream_cls):
        seen["path"] = path
        seen["body"] = body
        return SimpleNamespace(
            content=[SimpleNamespace(type="text", text="收到")],
        )

    monkeypatch.setattr(anthropic.Anthropic, "post", fake_post)

    out = llm.chat(
        "anthropic",
        "",
        "test-key",
        "claude-test",
        "system",
        ["hello"],
        temperature=0.2,
        max_tokens=256,
    )

    assert out == "收到"
    assert seen["path"] == "/v1/messages"
    assert seen["body"]["model"] == "claude-test"
    assert seen["body"]["messages"] == [{"role": "user", "content": "hello"}]
    assert "temperature" not in seen["body"]


def test_anthropic_thinking_uses_real_sdk_signature(monkeypatch):
    seen = {}

    def fake_post(self, path, *, body, options, cast_to, stream, stream_cls):
        seen["body"] = body
        return SimpleNamespace(
            content=[
                SimpleNamespace(type="thinking", thinking="..."),
                SimpleNamespace(type="text", text="好的"),
            ],
        )

    monkeypatch.setattr(anthropic.Anthropic, "post", fake_post)

    out = llm.chat(
        "anthropic",
        "",
        "test-key",
        "claude-test",
        "system",
        ["hello"],
        thinking=True,
    )

    assert out == "好的"
    assert seen["body"]["thinking"] == {
        "type": "enabled",
        "budget_tokens": llm._THINK_BUDGET,
    }
    assert "temperature" not in seen["body"]
