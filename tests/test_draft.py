from core import draft


def _capture(monkeypatch, api_type_expected):
    seen = {}

    def fake_chat(api_type, base_url, api_key, model, system, turns, **kwargs):
        assert api_type == api_type_expected
        seen.update(kwargs)
        return '["甲","乙","丙"]'

    monkeypatch.setattr(draft, "chat", fake_chat)
    return seen


def test_non_supporting_provider_ignores_thinking(monkeypatch):
    seen = _capture(monkeypatch, "openai")
    out = draft.draft_candidates(
        [("her", "在吗")], "friends", provider="moonshot", model="kimi-k3",
        thinking=True, api_key="sk-test",
    )

    assert out == ["甲", "乙", "丙"]
    assert seen["temperature"] == 1.0
    assert seen["max_tokens"] == 400
    assert seen["thinking"] is False


def test_anthropic_keeps_native_thinking_budget(monkeypatch):
    seen = _capture(monkeypatch, "anthropic")
    draft.draft_candidates(
        [("her", "在吗")], "friends", provider="anthropic", model="claude-test",
        thinking=True, api_key="sk-test",
    )

    assert seen["temperature"] == 1.0
    assert seen["max_tokens"] == 4000
    assert seen["thinking"] is True
