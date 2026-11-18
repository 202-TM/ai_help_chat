# ai_help_chat

聊天回复辅助：读取当前聊天窗口（本地离线 OCR），判断对方意图、情绪和风险，生成 3 条候选回复，填入输入框；**发送永远手动**。

本仓库基于 [jev-chat/jev-chat-windows](https://github.com/jev-chat/jev-chat-windows) 的 MIT 源码整理，主要改动：

- 移除 OpenRouter 接入，判断和起草都不再依赖 OpenRouter。
- 起草层统一为两种 **API 类型**：`openai`（OpenAI Chat Completions 兼容）和 `anthropic`（Anthropic Messages 兼容）。
- 内置国产 OpenAI 兼容预设：DeepSeek、Moonshot/Kimi、智谱 GLM、通义千问、硅基流动、阶跃星辰、百川智能。
- JEV/TypeSafe 判断改为**可选增强**：不填 `JEV_API_KEY` 时，自动复用起草 API 回答同一套判断问题。
- 修复切换来源后继续沿用旧密钥、旧模型或旧 Base URL 的问题。
- 增加发送前的本地规则脱敏，并保留设置开关。

## 功能

- **先判断再起草**：先判断对方真实意图、危险程度、该采取的动作，再生成 3 条候选。
- **多平台采集**：Windows 用窗口截图 + RapidOCR；支持微信 PC 主窗口，其他聊天窗口可在 `app/chatapps.py` 里适配。
- **本地 OCR**：截图只在内存中，不写磁盘、不上传；只有对话文本会发给你配置的模型接口。
- **手动发送**：只把候选填入输入框，不按回车、不点发送，不碰转账/红包。
- **发送前脱敏**：默认在调用模型前替换手机号、邮箱、身份证、银行卡和群昵称。
- **自定义 API**：任何 OpenAI 兼容或 Anthropic 兼容服务都能填 Base URL、模型 id 和密钥接入。
- **来源切换安全**：切换来源或自定义 Base URL 后旧密钥不再被误用；模型和地址会按新范围重置。

## 快速开始

### 1. 准备密钥

只需要一把起草密钥：

- 默认 DeepSeek：[platform.deepseek.com/api_keys](https://platform.deepseek.com/api_keys)
- 其他国产来源：在对应控制台创建 OpenAI 兼容 API Key
- Anthropic 兼容：Claude 或兼容网关的 Key

可选：TypeSafe JEV 判断密钥，[console.typesafe.ai](https://console.typesafe.ai/)。不填也能用，程序会用起草模型做判断。

### 2. 启动

下载 Release 的 zip，解压后运行 `jev-chat-windows.exe`；或从源码运行：

```bash
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python main.py
```

首次启动打开设置页：

1. 选择「你们的关系」。
2. 在「起草 · 语言模型」里选择来源，填 API Key。
3. 来源没有默认模型时，点「获取模型」选一个，或手动输入模型 id。
4. 可选：在「判断 · Jev」里填 TypeSafe Key；留空则复用起草 API。
5. 保存。

### 3. 使用

打开 PC 微信聊天窗口，保持窗口不最小化。对方来新消息后，悬浮窗会给判断摘要和 3 条候选；点「填入」，自己检查、修改、发送。

## API 类型与预设

| 预设 | API 类型 | Base URL | 默认模型 |
| --- | --- | --- | --- |
| DeepSeek 官网 | openai | `https://api.deepseek.com` | `deepseek-flash` |
| Moonshot (Kimi) | openai | `https://api.moonshot.cn/v1` | 需获取/手填 |
| 智谱 GLM | openai | `https://open.bigmodel.cn/api/paas/v4` | 需获取/手填 |
| 通义千问 | openai | `https://dashscope.aliyuncs.com/compatible-mode/v1` | 需获取/手填 |
| 硅基流动 | openai | `https://api.siliconflow.cn/v1` | 需获取/手填 |
| 阶跃星辰 | openai | `https://api.stepfun.com/v1` | 需获取/手填 |
| 百川智能 | openai | `https://api.baichuan-ai.com/v1` | 需获取/手填 |
| Anthropic | anthropic | `https://api.anthropic.com` | 需获取/手填 |
| 自定义 · OpenAI 兼容 | openai | 自己填 | 自己填 |
| 自定义 · Anthropic 兼容 | anthropic | 自己填 | 自己填 |

预设只是地址和协议快捷方式；接口新增模型不用改代码，直接手填模型 id。
自定义 OpenAI 兼容地址通常以 `/v1` 结尾；Anthropic SDK 会自行追加 `/v1/messages`，
所以自定义 Anthropic 地址一般填到网关根路径，不要重复加 `/v1`。

## 设置说明

配置文件在可执行文件旁边的 `config.json`；密钥只写 Windows 用户环境变量
`HKCU\Environment`，不出现在 `config.json`、日志或截图里。
从旧版升级且已有 `LLM_API_KEY` 时，若配置里还没有密钥指纹，程序会要求重新填写一次 key，以确认它确实属于当前来源。

| 设置 | 说明 | 配置字段 |
| --- | --- | --- |
| 你们的关系 | 恋人/朋友/同事/家人/自定义 | `relationship` |
| 参考上下文 | 判断和起草各看最近多少条，3~30 | `context` |
| 说话风格 | 一句话描述你的口吻，只喂给起草 | `style` |
| 起草来源 | 预设 key，见上表 | `draft_provider` |
| 起草 Base URL | 仅自定义来源需要 | `draft_base_url` |
| 起草模型 | 模型 id | `draft_model` |
| 判断来源 | 目前只有 TypeSafe，可选 | `jev_provider` |
| 判断模型 | 默认 `jev-latest` | `jev_model` |
| 密钥归属 | 当前 LLM 密钥是为哪个来源填的 | `key_owner` |
| 密钥地址归属 | 自定义来源的密钥绑定的 Base URL | `key_base_url` |
| 密钥指纹 | 校验环境变量里的 key 与当前来源是否仍是同一次保存，不保存原文 | `key_fingerprint` |
| 群聊指定回复对象 | 群聊里按某个人写候选 | `reply_target` |
| 发送前脱敏 | 发送前替换常见敏感信息，默认开 | `redact_sensitive` |
| 思考模式 | 更慢更贵，默认关 | `thinking` |
| 启动检查更新 | 只查 GitHub 版本号，可关 | `check_update` |
| 调试视图 | 显示 OCR 识别框，默认关 | `debug_view` |

## 隐私与边界

- 只读取自己电脑上、自己本来就有权查看的当前聊天窗口。
- 截图只在内存中，本地 RapidOCR 识别，不写磁盘、不上传。
- 发送给模型的内容：最近 N 条对话文本、关系设置、你最近 12 条 60 字以内的短消息（口吻样本）、你填的说话风格；群聊指定对象时再加一个对象名。
- 默认在发送前做规则脱敏：手机号、邮箱、身份证、银行卡、座机和群昵称会替换为占位符；截图、本地记录和填入框仍保留原文。
- 切换来源时，配置里的密钥指纹会与实际环境变量核对；保存中断或注册表写入失败时旧 key 会被拒绝，要求重新填写。
- 没有项目自建服务器，请求直接发往你配置的模型接口。
- 不自动发送；不碰转账、红包、收款界面。
- API Key 只进环境变量/注册表；报错文本会脱敏。

## 项目结构

```text
app/                 Qt 悬浮窗、设置页、截图/OCR 子进程、填入逻辑
core/                与 UI 无关的分析链
  providers.py       API 类型与预设表
  llm.py             OpenAI / Anthropic 两种 SDK 适配
  judge.py           用起草模型做判断的 JSON 适配
  privacy.py         发送前的本地规则脱敏
  jev_client.py      可选 JEV/TypeSafe 客户端
  engine.py          判断 → 起草 → 排序
  questions.py       判断题、状态构造、判断小抄
  draft.py           起草 3 条候选
docs/                设计和平台说明
probe/               只用于开发排查的探针
tools/               界面预览和端到端 demo
```

## 测试

```bash
.venv\Scripts\python -m pytest -q
```

测试覆盖：

- API 类型/预设表不变式，确保 OpenRouter 不再出现；
- 来源切换后的模型、Base URL、密钥归属；
- LLM 判断 JSON 的解析、choice key 校验和分数夹取；
- engine 在 JEV 不可用时自动降级到起草 API。
- 手机号、邮箱、证件、银行卡和群昵称脱敏，以及 engine 调用前的集成边界。

## 打包

```bash
build.bat
```

产物在 `dist/`。exe 未签名，Windows SmartScreen 可能提示；介意就自己从源码打包。

## 已知限制

- 微信 PC 窗口布局变化可能导致 OCR 识别失败，需要更新 `app/chatapps.py` 里的适配。
- 只支持 OpenAI / Anthropic 两类协议；其他协议请用自定义兼容网关。
- 判断质量取决于所选模型；小模型可能给出泛化建议，重要对话仍要自己判断。
- 脱敏是规则过滤，不等同于完整匿名化；地址、真实姓名等自由文本仍可能进入模型请求，可在设置里关闭或自行修改源码。
- 不提供自动发送，也不建议做自动发送：个人微信没有官方 API，自动化有封号风险。

## 许可与归属

MIT License。原始项目：[jev-chat/jev-chat-windows](https://github.com/jev-chat/jev-chat-windows)。
本仓库保留原始 `LICENSE` 和 `NOTICE`；衍生修改同样按 MIT 发布。
