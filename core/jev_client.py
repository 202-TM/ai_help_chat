# -*- coding: utf-8 -*-
"""可选的 JEV 判断客户端：TypeSafe 直连。

没有配置 ``JEV_API_KEY`` 时，engine 会退回复用起草模型做判断；配置了就走官方
``typesafe_sdk``。两条路返回同一个 dict 形状，engine 不关心跑的是哪条。
key 只从环境变量/注册表读，绝不打进日志。
"""
from __future__ import annotations

import os
from typing import NoReturn

try:  # 当模块导入 / 当脚本直接跑 都能用
    from .providers import ENV_VARS, JEV_ENV, JEV_PROVIDERS, TYPESAFE_BASE
except ImportError:
    from providers import ENV_VARS, JEV_ENV, JEV_PROVIDERS, TYPESAFE_BASE


class JevError(Exception):
    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


def redact_secrets(text: str) -> str:
    """Strip every live key from any string before print or disk write."""
    if not isinstance(text, str):
        text = str(text)
    for env in ENV_VARS:
        key = os.environ.get(env) or ""
        if key:
            text = text.replace(key, "[REDACTED]")
    return text


def _status_of(exc: Exception) -> int | None:
    """各家 SDK 放 HTTP 状态码的属性名不一样：openai/anthropic 是 status_code，
    typesafe 是 status。"""
    for name in ("status_code", "code", "status"):
        value = getattr(exc, name, None)
        if isinstance(value, int):
            return value
    return None


def _fail(exc: Exception, what: str) -> NoReturn:
    """SDK 抛的异常 → 一句人话的 JevError。消息过脱敏，绝不把 key 带出来。"""
    if isinstance(exc, JevError):
        raise exc
    status = _status_of(exc)
    hint = {401: "密钥被拒", 403: "没有权限", 404: "模型或地址不对", 422: "请求被拒",
            429: "被限流", 529: "服务过载"}.get(status, "")
    detail = redact_secrets(str(exc)).strip()[:300]
    head = f"{what} HTTP {status}" if status else f"{what}失败"
    raise JevError(f"{head}: {hint or detail or type(exc).__name__}", status) from None


def _api_key(env: str = JEV_ENV) -> str:
    """取 JEV 或起草密钥；旧变量迁移由 app.settings 在确认归属后处理。"""
    key = (os.environ.get(env) or "").strip()
    if not key:
        raise JevError(
            f"{env} is not set. Export it in the environment; "
            "do not put the key in a file."
        )
    return key


def ask(state: dict, questions: dict, timeout: float = 20,
        provider: str = "typesafe", model: str | None = None) -> dict:
    """问 JEV 一轮判断，返回 ``{"answers": {名字: 答案}, "usage": {...}}``。

    provider 目前只有 ``typesafe``；model=None 用默认模型。
    """
    spec = JEV_PROVIDERS.get(provider) or JEV_PROVIDERS["typesafe"]
    key = _api_key(JEV_ENV)
    return _ask_typesafe(state, questions, key, model or spec.default, timeout)


def _answer(answer) -> dict:
    """SDK 的答案对象 → engine 统一消费的 dict。"""
    if answer.type == "noul":
        return {"type": "noul", "noul": answer.noul}
    if answer.type == "choice":
        return {"type": "choice", "choice": answer.choice, "confidence": answer.confidence,
                "probabilities": dict(answer.probabilities)}
    # score：SDK 把概率的 key 转成了 int，这里转回字符串
    return {"type": "score", "score": answer.score, "confidence": answer.confidence,
            "probabilities": {str(k): v for k, v in answer.probabilities.items()}}


def _ask_typesafe(state: dict, questions: dict, key: str, model: str, timeout: float) -> dict:
    """官方 typesafe_sdk；重试用 RetryPolicy 默认值。"""
    import typesafe_sdk

    try:
        with typesafe_sdk.TypeSafeClient(api_key=key, base_url=TYPESAFE_BASE, model=model,
                                         timeout=timeout) as client:
            result = client.system_one(state, questions, model=model)
    except Exception as exc:
        _fail(exc, "JEV 判断")
    return {
        "answers": {name: _answer(a) for name, a in result.answers.items()},
        "usage": {"input_tokens": result.usage.input_tokens,
                  "output_tokens": result.usage.output_tokens},
    }


def list_models(provider: str, key: str, timeout: float = 10) -> list[str]:
    """TypeSafe 能用的 JEV 模型 id，去重排序。失败抛 JevError。"""
    if provider != "typesafe":
        raise JevError(f"unknown JEV provider: {provider!r}")
    import typesafe_sdk

    try:
        with typesafe_sdk.TypeSafeClient(api_key=key, base_url=TYPESAFE_BASE,
                                         timeout=timeout) as client:
            return sorted({m.name for m in client.models.list().models})
    except Exception as exc:
        _fail(exc, "取模型列表")


if __name__ == "__main__":
    # 不联网：把 SDK 边界换成假客户端，验 key 读取、答案映射和脱敏。
    import types as _t
    from unittest.mock import patch

    os.environ.pop(JEV_ENV, None)
    os.environ["DEEPSEEK_API_KEY"] = "sk-secret"
    assert redact_secrets("bad sk-secret") == "bad [REDACTED]"
    os.environ[JEV_ENV] = "ts-key"
    assert _api_key(JEV_ENV) == "ts-key"

    class _Answer:
        type = "choice"
        choice = "casual_chat"
        confidence = 0.8
        probabilities = {"casual_chat": 0.8}

    class _Client:
        def __init__(self, **kw):
            self.kw = kw

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def system_one(self, state, questions, model=None):
            return _t.SimpleNamespace(
                answers={"true_intent": _Answer()},
                usage=_t.SimpleNamespace(input_tokens=1, output_tokens=2),
            )

    fake = _t.SimpleNamespace(TypeSafeClient=_Client)
    with patch.dict("sys.modules", {"typesafe_sdk": fake}):
        out = ask({"chat": {}}, {"true_intent": {}})
    assert out["answers"]["true_intent"]["choice"] == "casual_chat"
    assert out["usage"] == {"input_tokens": 1, "output_tokens": 2}
    print("jev ok")
