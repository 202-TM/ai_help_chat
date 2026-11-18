# -*- coding: utf-8 -*-
"""两种 API 类型的薄适配层，一律走官方 SDK：

- ``openai``    OpenAI Chat Completions（`openai`）
- ``anthropic`` Anthropic Messages（`anthropic`）

只做两件事：``chat()`` 发一轮对话拿文本，``list_models()`` 列模型。
base_url / key / model 全由调用方传，本层不认识任何厂商名——厂商表在 core/providers.py。
出错一律转成 JevError，消息过脱敏。
"""
from __future__ import annotations

try:  # 当模块导入 / 当脚本直接跑 都能用
    from .jev_client import JevError, _fail
except ImportError:
    from jev_client import JevError, _fail

# Anthropic 开思考模式时的预算：起草三句话用不上更多；max_tokens 必须比它大，下面会兜住
_THINK_BUDGET = 2048


def _turns(user_turns: list[str], assistant: str = "assistant") -> list[dict]:
    """[user, assistant, user, …] 交替；第一条和最后一条都是用户。"""
    return [{"role": assistant if i % 2 else "user", "content": text}
            for i, text in enumerate(user_turns)]


def chat(api_type: str, base_url: str | None, api_key: str, model: str, system: str,
         user_turns: list[str], *, temperature: float = 1.0, max_tokens: int = 400,
         thinking: bool = False, extra_body: dict | None = None,
         headers: dict | None = None, timeout: float = 30) -> str:
    """发一轮对话，返回模型输出的纯文本。

    user_turns: 用户/助手交替的文本，奇数条，首尾都是用户说的（追问补齐候选就是 3 条）。
    thinking: 思考模式。OpenAI 协议没有统一字段，各家自己的开关由调用方经 extra_body 带进来；
              anthropic 是协议自带的参数，这里直接处理。
    """
    if api_type == "anthropic":
        return _anthropic(base_url, api_key, model, system, user_turns,
                          temperature, max_tokens, thinking, timeout)
    if api_type != "openai":
        raise JevError(f"unsupported api_type: {api_type!r}")
    return _openai(base_url, api_key, model, system, user_turns,
                   temperature, max_tokens, extra_body, headers, timeout)


def _openai(base_url, api_key, model, system, user_turns, temperature, max_tokens,
            extra_body, headers, timeout) -> str:
    import openai

    try:
        client = openai.OpenAI(base_url=base_url or None, api_key=api_key,
                               timeout=timeout, max_retries=2,
                               **({"default_headers": headers} if headers else {}))
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": system}] + _turns(user_turns),
            temperature=temperature, max_tokens=max_tokens,
            stream=False,  # DeepSeek 要显式关；别家无所谓
            **({"extra_body": extra_body} if extra_body else {}))
    except Exception as exc:
        _fail(exc, "起草")
    return resp.choices[0].message.content or ""


def _anthropic(base_url, api_key, model, system, user_turns, temperature, max_tokens,
               thinking, timeout) -> str:
    import anthropic

    extra = {}
    if thinking:
        extra["thinking"] = {"type": "enabled", "budget_tokens": _THINK_BUDGET}
        max_tokens = max(max_tokens, _THINK_BUDGET + 1024)  # max_tokens 得装得下思考 + 正文
    try:
        client = anthropic.Anthropic(base_url=base_url or None, api_key=api_key,
                                     timeout=timeout, max_retries=2)
        message = client.messages.create(model=model, system=system,
                                         messages=_turns(user_turns), max_tokens=max_tokens,
                                         **extra)
    except Exception as exc:
        _fail(exc, "起草")
    # 开了思考的话前面还有 thinking 块，只取文本块
    return "".join(b.text for b in message.content if getattr(b, "type", "") == "text")


def list_models(api_type: str, base_url: str | None, api_key: str,
                timeout: float = 10, headers: dict | None = None) -> list[str]:
    """某个地址上能用的模型 id，去重排序。失败抛 JevError，消息直接显示在设置页上。"""
    if api_type == "anthropic":
        import anthropic

        try:
            client = anthropic.Anthropic(base_url=base_url or None, api_key=api_key,
                                         timeout=timeout, max_retries=1)
            ids = [m.id for m in client.models.list()]
        except Exception as exc:
            _fail(exc, "取模型列表")
    elif api_type == "openai":
        import openai

        try:
            client = openai.OpenAI(base_url=base_url or None, api_key=api_key,
                                   timeout=timeout, max_retries=1,
                                   **({"default_headers": headers} if headers else {}))
            ids = [m.id for m in client.models.list()]
        except Exception as exc:
            _fail(exc, "取模型列表")
    else:
        raise JevError(f"unsupported api_type: {api_type!r}")
    return sorted(set(ids))


if __name__ == "__main__":
    # 不联网。在 SDK 边界上把客户端换成假的，只验「喂给 SDK 的参数对不对」。
    import os
    import types as _t

    import anthropic
    import openai

    seen: dict = {}

    def _fake(kind):
        def make(**kw):
            seen[kind + ".init"] = kw

            def call(**k):
                seen[kind + ".call"] = k
                if kind == "openai":
                    return _t.SimpleNamespace(choices=[_t.SimpleNamespace(
                        message=_t.SimpleNamespace(content='["甲","乙","丙"]'))])
                return _t.SimpleNamespace(content=[
                    _t.SimpleNamespace(type="thinking", thinking="…"),
                    _t.SimpleNamespace(type="text", text="嗯")])

            listing = {
                "openai": [_t.SimpleNamespace(id="b"), _t.SimpleNamespace(id="a"),
                           _t.SimpleNamespace(id="a")],
                "anthropic": [_t.SimpleNamespace(id="claude-y"), _t.SimpleNamespace(id="claude-x")],
            }[kind]
            models = _t.SimpleNamespace(list=lambda **_: listing)
            return _t.SimpleNamespace(
                models=models, messages=_t.SimpleNamespace(create=call),
                chat=_t.SimpleNamespace(completions=_t.SimpleNamespace(create=call)))
        return make

    openai.OpenAI, anthropic.Anthropic = _fake("openai"), _fake("anthropic")

    out = chat("openai", "https://api.deepseek.com", "sk-ds", "deepseek-flash", "S", ["U"],
               temperature=1.2, max_tokens=400, extra_body={"thinking": {"type": "disabled"}})
    assert out == '["甲","乙","丙"]'
    assert seen["openai.init"]["base_url"] == "https://api.deepseek.com"
    assert seen["openai.init"]["api_key"] == "sk-ds" and seen["openai.init"]["max_retries"] == 2
    assert seen["openai.call"]["model"] == "deepseek-flash"
    assert seen["openai.call"]["extra_body"] == {"thinking": {"type": "disabled"}}
    assert seen["openai.call"]["temperature"] == 1.2 and seen["openai.call"]["max_tokens"] == 400
    assert seen["openai.call"]["messages"] == [
        {"role": "system", "content": "S"}, {"role": "user", "content": "U"}]
    chat("openai", "https://api.moonshot.cn/v1", "k", "kimi", "S", ["U"], extra_body={})
    assert "extra_body" not in seen["openai.call"]
    chat("openai", "https://example.test/v1", "k", "m", "S", ["U"],
         headers={"User-Agent": "ai_help_chat"})
    assert seen["openai.init"]["default_headers"] == {"User-Agent": "ai_help_chat"}
    chat("openai", "https://api.deepseek.com", "k", "m", "S", ["U"])
    assert "default_headers" not in seen["openai.init"]
    chat("openai", "", "k", "m", "S", ["U1", "A1", "U2"])
    assert [m["role"] for m in seen["openai.call"]["messages"]] == [
        "system", "user", "assistant", "user"]
    assert seen["openai.init"]["base_url"] is None

    assert chat("anthropic", "https://api.anthropic.com", "sk-an", "claude-x", "S", ["U"],
                temperature=1.2, max_tokens=400) == "嗯"
    assert seen["anthropic.call"]["system"] == "S"
    assert "thinking" not in seen["anthropic.call"]
    assert "temperature" not in seen["anthropic.call"]
    assert seen["anthropic.call"]["messages"] == [{"role": "user", "content": "U"}]
    chat("anthropic", "https://api.anthropic.com", "sk-an", "claude-x", "S", ["U"],
         temperature=0.3, max_tokens=400)
    assert "temperature" not in seen["anthropic.call"]
    chat("anthropic", "", "k", "claude-x", "S", ["U"], temperature=1.2, max_tokens=400,
         thinking=True)
    assert seen["anthropic.call"]["thinking"] == {"type": "enabled", "budget_tokens": _THINK_BUDGET}
    assert "temperature" not in seen["anthropic.call"]
    assert seen["anthropic.call"]["max_tokens"] > _THINK_BUDGET

    assert list_models("openai", "https://x/v1", "k") == ["a", "b"]
    list_models("openai", "https://x/v1", "k", headers={"User-Agent": "ai_help_chat"})
    assert seen["openai.init"]["default_headers"] == {"User-Agent": "ai_help_chat"}
    assert list_models("anthropic", "", "k") == ["claude-x", "claude-y"]

    os.environ["DEEPSEEK_API_KEY"] = "sk-secret"

    class _Boom(Exception):
        status_code = 401

    def _explode(**kw):
        raise _Boom("bad key sk-secret")

    openai.OpenAI = _explode
    try:
        chat("openai", "", "sk-secret", "m", "S", ["U"])
        raise SystemExit("应当抛错")
    except JevError as e:
        assert e.status == 401 and "密钥被拒" in str(e) and "sk-secret" not in str(e)
    print("llm ok")
