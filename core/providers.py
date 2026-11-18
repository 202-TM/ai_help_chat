# -*- coding: utf-8 -*-
"""API 接入表：可选的 JEV 判断 + 按 API 类型接入的起草模型。

起草层只认两种 API 类型：
- ``openai``    OpenAI Chat Completions 兼容接口（DeepSeek、Kimi、GLM、通义、硅基流动等）
- ``anthropic`` Anthropic Messages 兼容接口（Claude 及兼容网关）

国产厂商只要兼容其中一种协议，就能直接选预设；不在表里的服务用「自定义」填
Base URL、模型 id 和密钥即可。密钥永远由调用方从环境变量/注册表读取，本文件不出现 key。
"""
from __future__ import annotations

from collections import namedtuple

JEV_ENV = "JEV_API_KEY"
LLM_ENV = "LLM_API_KEY"
# 迁移：老版本按来源存的 DeepSeek 变量。新变量空着时先用老的，保存一次就迁到新名字。
LEGACY = {LLM_ENV: "DEEPSEEK_API_KEY"}
TYPESAFE_BASE = "https://api.typesafe.ai"

# 判断层保留 JEV/TypeSafe 作为可选增强；不配置 JEV 时 engine 会用起草模型做判断。
_Jev = namedtuple("_Jev", "name default")
JEV_PROVIDERS = {
    "typesafe": _Jev("TypeSafe 直连（可选）", "jev-latest"),
}

_NONE = lambda on: {}  # noqa: E731
# api_type 只有 openai / anthropic 两种；base 空 = 自定义来源，必须由用户填写。
_Api = namedtuple("_Api", "name api_type base default extra headers keep",
                  defaults=(_NONE, None, None))

DRAFT_PROVIDERS = {
    "deepseek": _Api(
        "DeepSeek 官网", "openai", "https://api.deepseek.com", "deepseek-flash",
        lambda on: {"thinking": {"type": "enabled" if on else "disabled"}},
    ),
    "moonshot": _Api("Moonshot (Kimi)", "openai", "https://api.moonshot.cn/v1", ""),
    "zhipu": _Api("智谱 GLM", "openai", "https://open.bigmodel.cn/api/paas/v4", ""),
    "dashscope": _Api(
        "通义千问", "openai", "https://dashscope.aliyuncs.com/compatible-mode/v1", "",
    ),
    "siliconflow": _Api("硅基流动", "openai", "https://api.siliconflow.cn/v1", ""),
    "stepfun": _Api("阶跃星辰", "openai", "https://api.stepfun.com/v1", ""),
    "baichuan": _Api("百川智能", "openai", "https://api.baichuan-ai.com/v1", ""),
    "anthropic": _Api("Anthropic", "anthropic", "https://api.anthropic.com", ""),
    "custom_openai": _Api("自定义 · OpenAI 兼容", "openai", "", ""),
    "custom_anthropic": _Api("自定义 · Anthropic 兼容", "anthropic", "", ""),
}

API_TYPES = ("openai", "anthropic")
CUSTOM = ("custom_openai", "custom_anthropic")
DEFAULT_DRAFT = "deepseek"
# 设置页那句「只有 … 认思考开关」照着这里写
THINKING = ("DeepSeek 官网", "Anthropic")
ENV_VARS = sorted({JEV_ENV, LLM_ENV, *LEGACY.values()})


def get_draft(provider: str) -> _Api:
    """按 key 取起草配置；未知 key 退回默认，避免脏配置把程序打挂。"""
    return DRAFT_PROVIDERS.get(provider) or DRAFT_PROVIDERS[DEFAULT_DRAFT]


def get_jev(provider: str) -> _Jev:
    """按 key 取 JEV 配置；目前只有 TypeSafe 一条路。"""
    return JEV_PROVIDERS.get(provider) or JEV_PROVIDERS["typesafe"]


def is_custom(provider: str) -> bool:
    return provider in CUSTOM


if __name__ == "__main__":
    # 纯数据不变式：协议拼错、自定义漏 Base URL、默认来源被改掉最容易出问题。
    assert {p.api_type for p in DRAFT_PROVIDERS.values()} == set(API_TYPES)
    assert all(p.base or key in CUSTOM for key, p in DRAFT_PROVIDERS.items())
    assert all(not DRAFT_PROVIDERS[key].base for key in CUSTOM)
    assert next(iter(DRAFT_PROVIDERS)) == DEFAULT_DRAFT
    assert "openrouter" not in DRAFT_PROVIDERS and "openrouter" not in JEV_PROVIDERS
    assert DRAFT_PROVIDERS["deepseek"].extra(True) == {"thinking": {"type": "enabled"}}
    assert DRAFT_PROVIDERS["deepseek"].extra(False) == {"thinking": {"type": "disabled"}}
    assert DRAFT_PROVIDERS["moonshot"].extra(True) == {}
    assert get_draft("missing").name == DRAFT_PROVIDERS[DEFAULT_DRAFT].name
    print("providers ok")
