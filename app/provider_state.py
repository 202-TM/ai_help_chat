# -*- coding: utf-8 -*-
"""设置页的来源切换状态，纯函数，方便单测。

切换来源时必须同时处理三样东西：模型、Base URL、旧密钥归属。只改模型会让用户
拿 A 家的密钥打 B 家，或者把自定义 Base URL 带到预置来源上——这就是“切换轴”的问题。
"""
from __future__ import annotations

from core import providers


def switch_state(kind: str, provider: str, saved_provider: str, saved_model: str,
                 saved_base: str, table: dict) -> dict:
    """返回切换后应该填回的 model/base，以及是否清空密钥输入框。"""
    if kind == "jev":
        return {
            "model": saved_model if provider == saved_provider else table[provider].default,
            "base": "",
            "clear_key": False,
        }
    return {
        "model": saved_model if provider == saved_provider else (table[provider].default or ""),
        "base": saved_base if (provider == saved_provider and providers.is_custom(provider)) else "",
        "clear_key": True,
    }


def key_state(provider: str, owner: str, has_key: bool, any_key: bool | None = None) -> dict:
    """密钥属于别的来源/地址，或存在但不能用于当前范围时，都提示重填。"""
    if any_key is None:
        any_key = has_key
    mismatch = bool(owner and owner != provider) or (bool(any_key) and not has_key)
    return {"mismatch": mismatch, "configured": bool(has_key) and not mismatch}


def fetch_is_current(ticket: tuple[str, str, int] | None,
                     pending: tuple[str, str, int] | None) -> bool:
    """后台取模型的回包是否仍属于当前来源、地址和当前一次请求。

    用户切来源、改 Base URL、重新加载设置或发起新请求后，旧线程才回来的结果
    必须丢掉；否则 A 家/A 地址的模型列表会填进刚切换到的 B 家/B 地址。
    """
    return bool(ticket) and ticket == pending
