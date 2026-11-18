# -*- coding: utf-8 -*-
"""发送给模型前的本地脱敏。

这是规则过滤，不是完整匿名化：手机号、邮箱、身份证、银行卡、座机和群昵称会被
替换为占位符，地址、真实姓名等自由文本仍可能保留。调用方默认开启，用户可在设置
里关闭。
"""
from __future__ import annotations

import re

_EMAIL = re.compile(
    r"(?<![\w.+-])[\w.!#$%&'*+/=?^`{|}~-]+@"
    r"[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+",
    re.I,
)
_ID_CARD = re.compile(
    r"(?<![0-9A-Za-z])[1-9]\d{5}(?:18|19|20)\d{2}"
    r"(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])\d{3}[\dXx](?![0-9A-Za-z])"
)
_MOBILE = re.compile(r"(?<!\d)(?:\+?86[- ]?)?1[3-9]\d{9}(?!\d)")
_LANDLINE = re.compile(r"(?<!\d)(?:\+?86[- ]?)?0\d{2,3}[- ]?\d{7,8}(?!\d)")
_BANK_CARD = re.compile(r"(?<!\d)(?:\d[ -]?){15,18}\d(?!\d)")
_SECRET = re.compile(r"\b(?:sk|pk)-[A-Za-z0-9_-]{20,}\b")


def redact_text(text: str) -> str:
    """按固定顺序替换常见敏感信息；不依赖网络或第三方服务。"""
    value = str(text or "")
    value = _EMAIL.sub("[邮箱]", value)
    value = _ID_CARD.sub("[身份证号]", value)
    value = _MOBILE.sub("[手机号]", value)
    value = _LANDLINE.sub("[电话号码]", value)
    value = _BANK_CARD.sub("[银行卡号]", value)
    value = _SECRET.sub("[密钥]", value)
    return value


def redact_messages(messages: list, reply_to: str | None = None) -> tuple[list, str | None]:
    """脱敏消息正文，并把群成员昵称统一映射为「群成员A/B/...」。"""
    names: dict[str, str] = {}

    def name_for(raw: str) -> str:
        if raw not in names:
            index = len(names)
            suffix = chr(ord("A") + index) if index < 26 else str(index + 1)
            names[raw] = f"群成员{suffix}"
        return names[raw]

    cleaned = []
    for item in messages:
        if isinstance(item, dict):
            row = dict(item)
            row["text"] = redact_text(row.get("text"))
            if row.get("name"):
                row["name"] = name_for(str(row["name"]))
            cleaned.append(row)
            continue
        who, text = item[0], item[1]
        name = item[2] if len(item) > 2 and item[2] else None
        if name:
            cleaned.append((who, redact_text(text), name_for(str(name))))
        else:
            cleaned.append((who, redact_text(text)))

    mapped_reply = name_for(str(reply_to)) if reply_to else None
    return cleaned, mapped_reply


if __name__ == "__main__":
    sample = (
        "手机 13800138000，座机 010-12345678，邮箱 a.b+tag@example.com，"
        "身份证 11010519491231002X，卡号 6222 0212 3456 7890。"
    )
    out = redact_text(sample)
    assert "13800138000" not in out and "[手机号]" in out
    assert "010-12345678" not in out and "[电话号码]" in out
    assert "a.b+tag@example.com" not in out and "[邮箱]" in out
    assert "11010519491231002X" not in out and "[身份证号]" in out
    assert "6222 0212 3456 7890" not in out and "[银行卡号]" in out
    msgs, who = redact_messages([
        {"from": "her", "text": "13800138000", "name": "阿杰"},
        ("her", "a@example.com", "阿杰"),
    ], "阿杰")
    assert msgs[0]["name"] == msgs[1][2] == who == "群成员A"
    assert "13800138000" not in msgs[0]["text"] and "a@example.com" not in msgs[1][1]
    print("privacy ok")
