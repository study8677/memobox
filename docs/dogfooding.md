# MemoBox Dogfood 指南

这套 dogfood 的目标不是制造更多记忆，而是验证一个可量化的闭环：已有 `.memobox` 的项目在非简单任务开始时先读 index，模型按需复用旧记忆，任务结束只写高价值结构化结果，并能追溯实际复用过的 memory ids。

MemoBox 始终只暴露结构和维护文件一致性。相关性、是否打开、是否复用、是否值得写入，都由模型或用户判断。

## 实验范围

- 周期：连续两周。
- 项目：三个正在真实使用的项目，不要为实验虚构任务。
- 样本：至少 20 个已开启 MemoBox 的非简单真实任务。
- 对照：按 `evals/README.md` 使用 A（仓库/git）、B（宿主 Memories）、C（MemoBox）三组新会话；不要为了做对照而故意降低任务质量。
- 开启方式：用户明确选择后，在项目根目录运行一次 `memobox --store .memobox init`。此后 `.memobox` 就是该项目的 opt-in 信号。

简单查询、格式调整、一次性机械操作不进入有效样本。安全受限、包含秘密/凭据/个人数据或无法安全脱敏的任务既不读取也不写入 MemoBox，并记录为排除样本。

## 每个任务的流程

### 1. 开始前

在独立的实验表或 JSONL 运行日志中记录任务信息。实验指标不要写成 Memory Mail，否则会污染记忆质量。

建议字段：

```json
{
  "run_id": "2026-07-10-01",
  "project": "memobox",
  "task_class": "bug-fix",
  "non_trivial": true,
  "memobox_present": true,
  "index_read": false,
  "opened_memory_ids": [],
  "reused_memory_ids": [],
  "wrote_memory_id": null,
  "repeat_searches": 0,
  "time_to_first_correct_evidence_seconds": null,
  "correct": null,
  "excluded_reason": null,
  "notes": ""
}
```

`opened_memory_ids` 和 `reused_memory_ids` 必须分开。打开过不代表有用；只有真正改变计划、决策、实现或验证的记忆才算复用。

### 2. 任务开始

1. 确认 `.memobox` 已存在；不存在就正常执行任务，不自动初始化。
2. 非简单、非敏感任务先读取 `.memobox/index.json`。
3. 模型根据 index 中的标题、摘要、标签、状态和时间自行选择 id。MemoBox 不做排序或相关性判断。
4. 只打开被选择的 `mails/<id>.json`；只有需要证据时才打开 `traces/<id>.jsonl`。
5. 在运行日志里更新 `index_read`、`opened_memory_ids` 和实际生效的 `reused_memory_ids`。

### 3. 任务结束

先问五个问题：

- 是否形成了稳定决策或项目约束？
- 是否发现了非显而易见的根因，并验证了修复？
- 是否有能明显减少未来调查的精确文件、命令、URL 或证据？
- 是否有必须跨会话保留的重要风险或下一步？
- 是否形成了有价值的跨会话/跨 Agent 交接？

全部为“否”就不写。简单、敏感、仅推测、重复、无持久价值的任务也不写。通常每个任务写零条或一条；不要保存聊天流水账。

如果写入新 Memory Mail，将每个实际复用的旧 id 写入 `source_refs`：

```bash
memobox --store .memobox write \
  --subject "<short durable outcome>" \
  --summary "<one sentence useful from the index>" \
  --project "<project>" \
  --body "<verified context and result>" \
  --decision "<durable decision>" \
  --artifact "file:<exact path>" \
  --risk "<remaining caveat>" \
  --next-action "<unfinished follow-up>" \
  --source-ref "memobox:<reused-memory-id>" \
  --json
```

重复 `--source-ref` 可以记录多个实际复用 id。若任务不值得产生新记忆，只在实验运行日志记录复用，不要为了打点而新增低价值 Memory Mail。

### 4. PreCompact 处理

`PreCompact(auto)` 只是防止上下文压缩时完全丢失线索的 safety net：

- 它只应在已有 `.memobox` 的项目写入。
- 默认只保存筛选后的 hook 元数据和 git 状态，不保存完整 payload。
- 它可能拿不到完整 transcript，因此不能代替任务结束时的结构化总结。
- 它产生的 `needs_review` checkpoint 不直接算高质量写入。
- 每周复核 checkpoint：把确有持久价值的内容整理为正式 Memory Mail；其余标记 `stale` 或 `archived`。
- 敏感会话设置 `MEMOBOX_PRECOMPACT_DISABLED=1`；只有明确批准后才可设置 `MEMOBOX_PRECOMPACT_INCLUDE_PAYLOAD=1`。

## 指标定义

| 指标 | 计算方式 | 目标 |
| --- | --- | --- |
| Index-first 覆盖率 | 已先读 index 的有效任务 / 已开启 MemoBox 的非简单有效任务 | >= 95% |
| 实际复用率 | `reused_memory_ids` 非空的有效任务 / 全部有效任务 | 观察趋势，不以越高越好 |
| 复用可追溯率 | 有新 Memory Mail 且发生复用时，完整写入 `memobox:<id>` source refs 的任务 / 同类任务 | 100% |
| 重复调查下降 | baseline 平均重复搜索/命令数与 dogfood 阶段相比的下降比例 | >= 25% |
| 首个正确证据耗时 | 从任务开始到找到首个最终采用的正确文件、命令或来源 | 相比 baseline 下降 |
| 正确率 | 通过测试、人工复核或权威来源验证的任务 / 可验证任务 | 不低于 baseline |
| 记忆保留率 | 周审后保留的正式 Memory Mail / 新建正式 Memory Mail | >= 90% |
| 噪声率 | 周审判定为重复、无价值或不可复用的正式 Memory Mail / 新建正式 Memory Mail | <= 10% |
| Checkpoint 清理率 | 已复核的 `needs_review` PreCompact 记录 / 全部到期 checkpoint | 100% |
| 敏感数据事故 | 记忆中出现秘密、凭据、token、个人数据或未脱敏机密内容的次数 | 0 |

“重复搜索/命令”指上一条记忆已经明确给出正确答案，但任务仍为重新发现同一事实而执行的搜索或命令。正常验证不算重复调查。

## 每周复核

1. 直接读取 `.memobox/index.json`，抽查本周新增正式 Memory Mail。
2. 查看所有 `needs_review`、重复候选、过期风险和低价值记录；具体处理仍由模型或用户决定。
3. 检查复用链：

   ```bash
   jq -s '[.[] | .source_refs[]? | select(.kind == "memobox") | .ref] | unique' \
     .memobox/mails/*.json
   ```

4. 确认 `memobox:<id>` 指向仍存在的 Memory Mail，并抽查它确实影响了新任务结果。
5. 汇总本周指标，记录失败案例；不要只展示成功案例。

## 两周验收

达到以下条件才说明闭环值得扩大使用：

- 完成至少 20 个三项目真实有效任务。
- 重复调查至少下降 25%，且任务正确率不下降。
- 发生复用并产生新 Memory Mail 时，复用 id 的可追溯率为 100%。
- 正式记忆噪声率不超过 10%，敏感数据事故为 0。
- 能展示至少三个完整案例：旧 Memory Mail -> 新任务实际复用 -> 新结果与验证 -> `source_refs` 回链。

如果没有达到门槛，先调整 skill 的触发条件、写入模板和周审规则。不要优先用 MCP、数据库或 Web UI 掩盖“记忆没有被真实复用”的问题。

可重复执行的五个任务 fixture、结果 schema、示例数据和零依赖汇总脚本位于 [`evals/`](../evals/README.md)。示例结果只用于验证报表管道，不能作为产品有效性的证据。
