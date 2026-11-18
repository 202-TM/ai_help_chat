# -*- coding: utf-8 -*-
"""整条链的唯一入口：对话 → 判断 → 带着判断起草 3 条 → 排序 → 结构化结果。

判断优先走可选的 JEV/TypeSafe；没有 JEV key 或 JEV 调用失败时，自动复用起草模型
（OpenAI / Anthropic 兼容接口）回答同一套问题。这样只配一把国产 API key 也能用。
平台无关。SSE 消费者、悬浮窗、命令行 demo 都只调 analyze()。
"""
from __future__ import annotations

try:
    from .draft import draft_candidates
    from .jev_client import JevError, _api_key, ask
    from .judge import judge
    from .privacy import redact_messages, redact_text
    from .providers import LLM_ENV, get_draft
    from .questions import JUDGE_QUESTIONS, build_rank_question, build_state, guidance_text
except ImportError:
    from draft import draft_candidates
    from jev_client import JevError, _api_key, ask
    from judge import judge
    from privacy import redact_messages, redact_text
    from providers import LLM_ENV, get_draft
    from questions import JUDGE_QUESTIONS, build_rank_question, build_state, guidance_text

_REPLY_IDX = {"reply_a": 0, "reply_b": 1, "reply_c": 2}


def _add_usage(total: dict, one: dict | None) -> None:
    """多次判断调用的 usage 相加；非数字字段后来的盖掉前面的。"""
    for k, v in (one or {}).items():
        total[k] = total.get(k, 0) + v if isinstance(v, (int, float)) else v


def _judge_llm(state: dict, questions: dict, spec, base_url: str | None,
               model: str | None, timeout: float, api_key: str | None = None) -> dict:
    """用起草 API 做判断；key 缺失会抛 JevError，由调用方决定是否继续。"""
    key = api_key if api_key is not None else _api_key(LLM_ENV)
    return judge(state, questions, spec.api_type, base_url or spec.base, key,
                 model, timeout)


def analyze(messages: list, relationship: str, model: str | None = None,
            timeout: float = 30, context: int = 10, provider: str = "deepseek",
            base_url: str | None = None, reply_to: str | None = None, style: str = "",
            thinking: bool = False, jev_provider: str = "typesafe",
            jev_model: str | None = None, api_key: str | None = None,
            redact_sensitive: bool = True) -> dict:
    """messages: [(from, text)] from ∈ {her, me}，最新一条在最后；
    群聊里可以带第三项 name（说这句话的人），单聊不带。

    provider / model / base_url: 起草 API（core.providers.DRAFT_PROVIDERS）。
    jev_provider / jev_model: 可选 JEV 判断；没有 key 时自动改用起草 API。
    api_key: 设置层确认过来源/地址归属的起草 key；None 时源码工具才从环境变量取。
    redact_sensitive: 发送给模型前是否本地替换手机号、邮箱、证件/卡号和群昵称。
    reply_to: 群聊里指定回复给谁；None = 正常回复。
    style: 用户自己描述的说话风格，只影响起草。
    thinking: 起草时是否开思考模式，只影响起草，默认关。

    返回 {candidates, best_index, best_reply, scores, answers, usage, reply_to}。
    """
    spec = get_draft(provider)
    model = str(model or spec.default or "").strip()
    if not model:
        raise JevError(f"{spec.name} 需要先选择模型")
    model_reply_to = reply_to
    if redact_sensitive:
        messages, model_reply_to = redact_messages(messages, reply_to)
        relationship = redact_text(relationship)
        style = redact_text(style)
    state = build_state(messages, relationship, keep=context, reply_to=model_reply_to)
    usage: dict = {}
    answers: dict = {}
    judged = False
    used_jev = False

    try:
        first = ask(state, dict(JUDGE_QUESTIONS), timeout=timeout,
                    provider=jev_provider, model=jev_model)
        answers = first.get("answers") or {}
        _add_usage(usage, first.get("usage"))
        judged, used_jev = True, True
    except JevError:
        pass  # 没配 JEV 或调用失败：下面用起草 API 判断

    if not judged:
        try:
            first = _judge_llm(state, dict(JUDGE_QUESTIONS), spec, base_url, model, timeout,
                               api_key=api_key)
            answers = first.get("answers") or {}
            _add_usage(usage, first.get("usage"))
            judged = True
        except JevError:
            pass  # 判断失败也继续盲起草；起草本身会给出真正的错误

    candidates = draft_candidates(messages, relationship, provider=provider, model=model,
                                  base_url=base_url, timeout=timeout, keep=context,
                                  reply_to=model_reply_to, style=style, thinking=thinking,
                                  guidance=guidance_text(answers) if judged else None,
                                  api_key=api_key)
    if not candidates:  # 注入过滤可以把起草结果全扔掉
        raise JevError("起草结果没有可用候选回复")

    if len(candidates) >= 2:
        questions = build_rank_question(candidates)
        try:
            if used_jev:
                second = ask(state, questions, timeout=timeout,
                             provider=jev_provider, model=jev_model)
            else:
                second = _judge_llm(state, questions, spec, base_url, model, timeout,
                                    api_key=api_key)
            answers = {**answers, **(second.get("answers") or {})}
            _add_usage(usage, second.get("usage"))
        except JevError:
            second = {}  # 排不上序就按第一条推荐

    best_key = (answers.get("best_reply") or {}).get("choice")
    best_index = _REPLY_IDX.get(best_key, 0)
    if best_index >= len(candidates):
        best_index = 0

    probabilities = (answers.get("best_reply") or {}).get("probabilities") or {}
    scores = [0.0, 0.0, 0.0]
    for key, idx in _REPLY_IDX.items():
        try:
            scores[idx] = float(probabilities.get(key, 0.0))
        except (TypeError, ValueError):
            scores[idx] = 0.0

    return {
        "candidates": candidates,
        "best_index": best_index,
        "best_reply": candidates[best_index],
        "scores": scores,
        "answers": answers,
        "usage": usage,
        "reply_to": reply_to,
    }


if __name__ == "__main__":
    # 候选被过滤光时要抛 JevError；JEV 不可用时要用 LLM 判断。
    from unittest.mock import patch

    env = {"LLM_API_KEY": "k", "JEV_API_KEY": ""}
    with patch.dict("os.environ", env, clear=False), \
         patch("__main__.ask", side_effect=JevError("no jev")), \
         patch("__main__._judge_llm", return_value={"answers": {}, "usage": {}}), \
         patch("__main__.draft_candidates", return_value=[]):
        try:
            analyze([("her", "hello")], "friends")
            raise SystemExit("应当抛错")
        except JevError as e:
            assert "没有可用候选" in str(e)

    with patch.dict("os.environ", env, clear=False), \
         patch("__main__.ask", side_effect=JevError("no jev")), \
         patch("__main__._judge_llm", return_value={"answers": {}, "usage": {}}), \
         patch("__main__.draft_candidates", return_value=["甲", "乙", "丙"]):
        out = analyze([("her", "hello")], "friends")
    assert out["best_reply"] == "甲" and len(out["candidates"]) == 3
    print("engine ok")
