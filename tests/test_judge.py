import json

import pytest

from core import judge
from core.jev_client import JevError


QUESTIONS = {
    "true_intent": {
        "type": "choice",
        "criteria": {"casual_chat": "", "vent_anger": ""},
    },
    "danger_level": {"type": "score", "criteria": ["low", "high"]},
    "literal_question": {"type": "noul", "criteria": {}},
}


def test_parse_answers_rejects_invented_choice_and_clamps_score():
    data = {"answers": {
        "true_intent": {
            "type": "choice", "choice": "casual_chat", "confidence": 2,
            "probabilities": {"casual_chat": 1.4, "invented": 0.9},
        },
        "danger_level": {"type": "score", "score": 99, "confidence": -1},
        "literal_question": {"type": "noul", "noul": "false"},
    }}
    parsed = judge._parse_answers(data, QUESTIONS)
    assert parsed["true_intent"]["choice"] == "casual_chat"
    assert parsed["true_intent"]["confidence"] == 1.0
    assert parsed["true_intent"]["probabilities"] == {"casual_chat": 1.0}
    assert parsed["danger_level"]["score"] == 9.0
    assert parsed["danger_level"]["confidence"] == 0.0
    assert parsed["literal_question"]["noul"] is False


def test_parse_answers_drops_unknown_choice():
    data = {"answers": {"true_intent": {"type": "choice", "choice": "made_up"}}}
    assert judge._parse_answers(data, QUESTIONS) == {}


def test_json_object_tolerates_fences():
    assert judge._json_object('```json\n{"answers": {}}\n```') == {"answers": {}}


def test_judge_uses_chat_and_parses_json(monkeypatch):
    payload = json.dumps({"answers": {
        "true_intent": {"type": "choice", "choice": "casual_chat",
                        "confidence": 0.8,
                        "probabilities": {"casual_chat": 0.8, "vent_anger": 0.2}},
        "danger_level": {"type": "score", "score": 2, "confidence": 0.7},
    }})
    seen = {}

    def fake_chat(api_type, base_url, key, model, system, turns, **kwargs):
        seen.update(api_type=api_type, base_url=base_url, key=key, model=model)
        return payload

    monkeypatch.setattr(judge, "chat", fake_chat)
    out = judge.judge({"chat": {"messages": []}}, QUESTIONS, "openai",
                      "https://api.deepseek.com", "sk-test", "deepseek-flash")
    assert seen == {
        "api_type": "openai", "base_url": "https://api.deepseek.com",
        "key": "sk-test", "model": "deepseek-flash",
    }
    assert out["answers"]["true_intent"]["choice"] == "casual_chat"
    assert out["answers"]["danger_level"]["score"] == 2.0


def test_judge_requires_an_explicit_model():
    with pytest.raises(JevError, match="缺少模型"):
        judge.judge({}, QUESTIONS, "openai", None, "sk-test", "")
