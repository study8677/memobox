<div align="center">

# MemoBox

**An inbox-style memory layer for AI agents.**

让 Agent 先扫“记忆标题”，再按需打开正文和证据，而不是把历史对话整包塞进上下文。

[English](README-EN.md) · [文档结构](docs/schema.md) · [示例](examples/demo.py) · [GitHub](https://github.com/study8677/memobox)

[![CI](https://github.com/study8677/memobox/actions/workflows/ci.yml/badge.svg)](https://github.com/study8677/memobox/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue.svg)](pyproject.toml)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Status](https://img.shields.io/badge/status-alpha-orange.svg)](CHANGELOG.md)

<br/>

<img src="docs/assets/memobox-flow.svg" alt="MemoBox 邮箱式 index-first 记忆流程" width="860">

</div>

---

## MemoBox 是什么

MemoBox 是一个给 AI Agent 用的**任务级记忆盒**。它把每个完成的任务保存成一封结构化“记忆邮件”，让 Agent 下次工作时先扫轻量索引，再按需展开正文和原始证据。

它解决的是工程 Agent 最常见的长期记忆问题：

> 我们不缺历史记录，缺的是 Agent 能快速判断“哪段历史值得打开”的机制。

MemoBox 的默认策略很简单：

```text
打开 index.json 目录 -> 模型自己选择邮件 id -> 打开 mails/<id>.json -> 需要证据时才打开 traces/<id>.jsonl
```

## 为什么是“邮箱”

邮箱模型不是比喻装饰，而是 MemoBox 的核心交互：

- **标题就是最好的摘要**：邮件标题天然要求短、明确、可扫描；Memory Mail 的 `subject` 也是 Agent 第一眼应该读的内容。
- **收件箱就是轻量索引**：Agent 先扫 `index.json`，像人扫 inbox 一样判断哪封值得打开。
- **正文是渐进式加载**：Agent 先看完整目录，再自己决定打开哪些 `mails/<id>.json`。
- **附件/原文是证据层**：只有需要追溯时，才打开 `traces/<id>.jsonl`。
- **状态就是记忆生命周期**：`pinned`、`archived`、`stale`、`needs_review` 对应置顶、归档、过期和待复核。

这就是 MemoBox 的渐进式读取：

```text
标题 -> 摘要 -> 正文 -> 原始证据
```

这和 Agent skill 的工作方式相吻合：skill 不应该一次加载全部历史，而应该先读“标题层”的索引，再由模型决定展开哪些邮件。

第一版只专注四个承诺：

- **Index-first**：默认只打开 `index.json` 目录，避免把完整正文和证据塞进上下文。
- **Task-level memory**：按一次完成任务沉淀决策、产物、风险和后续动作。
- **Evidence-aware**：需要追溯时再打开 `Memory Mail` 或 `Raw Trace`。
- **Local-first Python**：零运行时依赖，CLI + Python API，JSON 文件可审计。

## 30 秒看懂

```bash
memobox --store .memobox add \
  --subject "Fix slow /orders API" \
  --summary "Found N+1 query pattern and added eager loading." \
  --project api-platform \
  --team backend \
  --role coding-agent \
  --tags performance,n-plus-one \
  --body "Changed OrderService query path and added regression test." \
  --decision "Prefer query-level fix before introducing cache."

memobox --store .memobox inbox --json
```

Agent 看到的第一层不是完整历史，而是这样的目录条目：

```json
{
  "subject": "Fix slow /orders API",
  "summary": "Found N+1 query pattern and added eager loading.",
  "project": "api-platform",
  "tags": ["performance", "n-plus-one"],
  "status": "inbox"
}
```

MemoBox 不判断哪条相关。Agent 看目录后自己决定是否打开对应正文或 raw trace。

## 为什么不是再做一个向量记忆库

| 常见记忆系统 | MemoBox |
| --- | --- |
| 偏用户偏好、事实片段、语义召回 | 偏任务、决策、证据、后续动作 |
| 经常直接依赖 embedding 召回 | 默认 directory-first，可解释、可审计 |
| 来源链不一定清晰 | 摘要 -> 正文 -> raw trace 可追溯 |
| 适合个人助手长期偏好 | 适合工程 Agent 和多 Agent 协作 |
| 历史越多越容易变成黑盒 | 像邮箱一样置顶、归档、标记过期 |

MemoBox 可以和 mem0、RAG、Obsidian、日志系统一起用。mem0 更适合记住用户偏好和事实，MemoBox 更适合保存 Agent 做过的工作。

## 核心能力

| 能力 | 说明 |
| --- | --- |
| Index-first inbox | `inbox` / `recall` 默认只列 `index.json` 目录，不打开正文和 raw trace |
| Task memory mail | 每个任务沉淀为一封可展开记忆邮件 |
| Raw trace on demand | 原始对话、命令、工具调用只在需要证据时读取 |
| Team-ready metadata | 内置 `project`、`workspace`、`team`、`role`、`participants` |
| Inbox workflow | 支持 `inbox`、`pinned`、`needs_review`、`archived`、`stale` |
| Local-first CLI | 纯 Python、JSON 文件、易接入现有 Agent |

## 架构

```mermaid
flowchart LR
    A["Agent request"] --> B["Scan MemoBox Index<br/>index.json"]
    B --> C{"Model chooses mail ids?"}
    C -- "No" --> D["Continue without opening bodies"]
    C -- "Yes" --> E["Open Memory Mail<br/>mails/&lt;id&gt;.json"]
    E --> F{"Need evidence?"}
    F -- "No" --> G["Use summary + body"]
    F -- "Yes" --> H["Open Raw Trace<br/>traces/&lt;id&gt;.jsonl"]
```

MemoBox 的三层文件结构：

| 层级 | 文件 | 放什么 |
| --- | --- | --- |
| MemoBox Index | `index.json` | 标题、摘要、项目、团队、角色、标签、状态、时间 |
| Memory Mail | `mails/<id>.json` | 背景、决策、产物、风险、后续动作、来源引用 |
| Raw Trace | `traces/<id>.jsonl` | 原始对话、工具调用、终端证据或外部事件 |

测试会验证：目录读取只返回 index 层信息，不会打开正文或 raw trace。

## 快速开始

```bash
git clone https://github.com/study8677/memobox.git
cd memobox
python3 -m pip install -e ".[test]"
```

初始化：

```bash
memobox --store .memobox init
```

添加记忆：

```bash
memobox --store .memobox add \
  --subject "MemoBox index-first retrieval" \
  --summary "Agent should scan the lightweight index before opening memory bodies." \
  --project memobox \
  --team platform \
  --role main-agent \
  --tags memory,agent,index-first \
  --body "Implemented index/body/raw-trace split and tests for lazy expansion." \
  --decision "Directory reads must never open raw traces by default."
```

打开记忆收件箱目录：

```bash
memobox --store .memobox inbox --json
```

展开正文：

```bash
memobox --store .memobox show <memory-id> --json
```

显式追溯 raw trace：

```bash
memobox --store .memobox raw <memory-id> --json
```

## Python API

```python
from memobox import JsonMemoBoxStore, MemoryMail

store = JsonMemoBoxStore(".memobox")

store.add_mail(
    MemoryMail(
        id="",
        subject="Agent memory design",
        summary="MemoBox stores task-level memory as index-first mail records.",
        project="memobox",
        team="platform",
        role="main-agent",
        tags=["agent-memory", "index-first"],
        context="Longer expandable body lives outside the index.",
        decisions=["Use task-level memory instead of turn-level memory for v1."],
    )
)

directory = store.list_index()
mail = store.open_mail(directory[0].id)
```

## Agent 接入方式

给 Agent 暴露三个基础工具就够了：

```python
def list_memobox_inbox() -> str:
    entries = store.list_index()
    return "\n".join(f"{entry.id}: {entry.subject} - {entry.summary}" for entry in entries)


def open_memory_mail(memory_id: str) -> str:
    mail = store.open_mail(memory_id)
    return mail.context


def open_raw_trace(memory_id: str) -> list[dict]:
    return store.open_raw_trace(memory_id)
```

推荐策略：

- 任务开始时先 `list_memobox_inbox`。
- 模型自己扫描标题、摘要、标签、状态和时间。
- 模型自己选择 id 后再 `open_memory_mail`。
- 只有需要证据链时才打开 raw trace。
- 任务结束时由主 Agent 或 memory curator agent 写入新的 Memory Mail。

## Agent Workflow

MemoBox 现在提供这些面向 Agent 生命周期的命令：

| 命令 | 触发时机 | 作用 |
| --- | --- | --- |
| `memobox inbox` / `memobox map` | 任务开始 | 打开当前项目的完整 index 目录，正文和证据只给位置 |
| `memobox recall` | 任务开始 | 打开项目记忆和全局记忆目录，模型自己决定打开哪些正文 |
| `memobox remember` | 任务结束 | 按标准 Memory Mail 格式写入本次任务记忆 |
| `memobox promote` | 经验可复用时 | 把项目记忆提升为全局经验 |
| `memobox curate` | 记忆整理时 | 查重、合并、标记 stale、置顶重要记忆 |

推荐的项目级和全局级布局：

```text
your-project/.memobox        # 当前项目记忆
~/.memobox-global            # 跨项目全局经验
```

也可以用环境变量指定全局记忆位置：

```bash
export MEMOBOX_GLOBAL_STORE="$HOME/.memobox-global"
```

任务开始时打开目录：

```bash
memobox --store .memobox recall \
  "README 高星项目首页结构" \
  --project memobox \
  --global-store ~/.memobox-global \
  --json
```

任务结束时记住：

```bash
memobox --store .memobox remember \
  --subject "Improve MemoBox README homepage" \
  --summary "Reworked README into a high-star style homepage with hero, demo, differentiation, workflow, and roadmap." \
  --project memobox \
  --team platform \
  --role memory-curator \
  --tags readme,github,open-source \
  --body "The README now leads with index-first task memory, then shows a 30-second demo and agent workflow." \
  --decision "Keep README.md Chinese-first and README-EN.md as the English version."
```

把项目经验提升为全局经验：

```bash
memobox --store .memobox promote <memory-id> \
  --global-store ~/.memobox-global \
  --tag readme-pattern
```

整理记忆：

```bash
memobox --store .memobox curate duplicates --json
memobox --store .memobox curate merge <id-a> <id-b> \
  --subject "Merged README homepage guidance" \
  --summary "Merged duplicate README optimization memories."
memobox --store .memobox curate stale <id>
memobox --store .memobox curate pin <id>
```

## Claude Code / Codex Plugin

MemoBox 第一版插件是 **skills-only plugin**：它不启动 MCP server，也不改 CLI 参数，而是让 Claude Code 和 Codex 知道什么时候调用现有 `memobox` 命令。

先安装 CLI：

```bash
python3 -m pip install --user git+https://github.com/study8677/memobox.git
```

Claude Code 安装：

```bash
claude plugin marketplace add study8677/memobox
claude plugin install memobox@memobox-marketplace --scope user
```

Codex 安装：

```bash
codex plugin marketplace add study8677/memobox
codex plugin add memobox@memobox-marketplace
```

安装后可以自然语言触发：

```text
用 MemoBox 打开这个项目的记忆收件箱
用 MemoBox 记录这次任务结论
用 MemoBox 整理重复记忆
```

也可以显式调用 skill：

```text
Claude Code: /memobox:recall
Claude Code: /memobox:remember
Codex: $memobox:recall
Codex: $memobox:remember
```

默认约定：

- 项目记忆：当前仓库 `.memobox`
- 全局记忆：`${MEMOBOX_GLOBAL_STORE:-$HOME/.memobox-global}`
- 召回只读索引目录；模型自己选择要打开的正文；只有需要证据时才打开 raw trace。

## 适合谁

- 编码 Agent：记住项目决策、文件路径、失败原因和修复方式。
- 运维 Agent：保存事故处理、命令证据、回滚步骤。
- 研究 Agent：沉淀研究结论、来源和待验证假设。
- 多 Agent 团队：共享任务级上下文，而不是共享整段聊天记录。
- 个人知识库用户：把对话历史整理成可维护的工作档案。

## Roadmap

**Storage**

- [x] 本地 JSON store
- [ ] SQLite backend
- [ ] Schema migration

**Retrieval**

- [x] index-first inbox/map directory
- [x] legacy lexical search command
- [ ] 更好的 inbox 分组、分页和生命周期视图
- [ ] stale memory detection

**Agent Integration**

- [x] CLI：`init`、`add`、`inbox`、`map`、`recall`、`search`、`show`、`status`、`raw`
- [x] Claude Code / Codex skills-only plugin
- [ ] Memory curator agent workflow
- [ ] MCP server for Codex、Claude Desktop、Cursor

**UX / Trust**

- [x] 中英文 README
- [ ] Privacy redaction hooks
- [ ] Web UI：像邮箱一样整理 Agent 记忆
- [ ] Social preview and visual identity

## 开发

```bash
python3 -m pip install -e ".[test]"
python3 -m pytest -q
PYTHONPATH=src python3 examples/demo.py
```

当前测试覆盖：

- 10 个历史任务模拟写入。
- 搜索只读取索引，不打开正文或 raw trace。
- `inbox` / `map` 只输出目录和正文/raw trace 位置。
- `recall` 同时打开项目和全局目录，不按 query 替模型过滤。
- 状态更新同步 index 和 body。
- CLI 回归：add -> inbox -> show -> status。

## 测试保障

MemoBox 的核心承诺是 index-first，因此测试不只验证输出，还验证读取路径：

- `inbox` / `recall` 只调用 `list_index()`。
- 目录输出不包含 `context`、`decisions` 或 raw trace 内容。
- `show` 才展开 `Memory Mail`。
- `raw` 或显式参数才读取 `Raw Trace`。

## 贡献

MemoBox 还处在 alpha 阶段，适合参与的方向：

- Agent 记忆评测集。
- mem0 / MCP / Obsidian 集成。
- 更好的 inbox 组织、过期和归档策略。
- 团队协作权限和审计模型。
- Web UI 和 social preview 设计。

详见 [CONTRIBUTING.md](CONTRIBUTING.md)。

## License

MIT License. See [LICENSE](LICENSE).
