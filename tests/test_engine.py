import pytest

from core import engine
from core.jev_client import JevError


def test_engine_falls_back_to_llm_judge(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "sk-test")
    calls = {"judge": 0}

    def no_jev(*args, **kwargs):
        raise JevError("no jev key")

    def fake_judge(state, questions, spec, base_url, model, timeout, api_key=None):
        calls["judge"] += 1
        return {"answers": {}, "usage": {}}

    monkeypatch.setattr(engine, "ask", no_jev)
    monkeypatch.setattr(engine, "_judge_llm", fake_judge)
    monkeypatch.setattr(engine, "draft_candidates",
                        lambda *a, **k: ["甲", "乙", "丙"])
    out = engine.analyze([("her", "hello")], "friends")
    assert calls["judge"] == 2  # 判断题 + 排序题
    assert out["best_reply"] == "甲"
    assert len(out["candidates"]) == 3


def test_engine_prefers_jev_when_available(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "sk-test")
    calls = {"judge": 0, "ask": 0}

    def fake_ask(state, questions, timeout=20, provider="typesafe", model=None):
        calls["ask"] += 1
        return {"answers": {}, "usage": {}}

    def fake_judge(*args, **kwargs):
        calls["judge"] += 1
        return {"answers": {}, "usage": {}}

    monkeypatch.setattr(engine, "ask", fake_ask)
    monkeypatch.setattr(engine, "_judge_llm", fake_judge)
    monkeypatch.setattr(engine, "draft_candidates",
                        lambda *a, **k: ["甲", "乙", "丙"])
    engine.analyze([("her", "hello")], "friends")
    assert calls == {"judge": 0, "ask": 2}


def test_engine_errors_when_all_candidates_are_filtered(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "sk-test")
    monkeypatch.setattr(engine, "ask", lambda *a, **k: (_ for _ in ()).throw(JevError("x")))
    monkeypatch.setattr(engine, "_judge_llm", lambda *a, **k: {"answers": {}, "usage": {}})
    monkeypatch.setattr(engine, "draft_candidates", lambda *a, **k: [])
    with pytest.raises(JevError, match="没有可用候选"):
        engine.analyze([("her", "hello")], "friends")


def test_engine_does_not_use_a_deepseek_model_for_anthropic(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "sk-test")
    with pytest.raises(JevError, match="需要先选择模型"):
        engine.analyze([("her", "hello")], "friends", provider="anthropic")
