---
name: wf-review
description: 在规划产物收敛后、进入派发前执行独立复核。派发两个上下文隔离的复核者（对抗型与一致性型），汇总报告、判定是否收敛、维护轮次记录。当用户说"复核""review""收敛""可以派发了吗"时使用。
---

# wf-review — 独立复核

流程权威是 `.trellis/workflow.md` 的 `[workflow-state:reviewing]` 块。本技能只说明**这一步怎么做**。

## 前置检查

全部满足才可开始，否则回到 `planning`：

- [ ] `prd.md` 存在，且验收标准可测。
- [ ] 若任务为复杂任务（存在 `design.md`），`design.md` 存在。
- [ ] `implement.jsonl` 与 `check.jsonl` 非空。
- [ ] `task.json` 的 `status` 已是 `reviewing`。

```bash
python .trellis/scripts/wf_status.py <task-dir> reviewing
```

## Step 1: 生成本轮输入清单

向两个复核者提供**完全相同的**输入清单。规则：

**必须包含**：

- `prd.md`、`design.md`（若存在）
- 本次涉及文件的真实内容路径
- 相关契约：API schema、DTO、表结构、前端类型定义、i18n 词条
- `.trellis/spec/` 中适用的条目
- 项目 `AGENTS.md` / `CLAUDE.md`

**Phase 0（greenfield）的输入差异**：

- 用 `stack.md` 替代 `prd.md`，`design.md` 仍需要。
- 额外提供：骨架的实际文件清单、`profile.commands` 的真实运行输出。
- **把选型的理由与限制一起提供**——这阶段没有代码可对照，只给结论的话复核者只能凭通用直觉判断，会漏掉项目特有的约束。
- 复核重点：选型是否自相矛盾、模块边界是否闭合、非功能约束是否被选型满足、不可逆决策是否被论证。

**绝不包含**：

- 作者的推理过程、自我辩护、"我已经考虑过 X"
- 上一轮的复核报告
- 会话历史摘要
- 之前的 `accepted-risks.md` 中已裁决条目的原有讨论

清单写成路径列表直接放进派发提示里，不要让复核者自己猜该读什么。

## Step 2: 并行派发

同一轮内派发两个复核者，**并行**，互相不可见对方的报告：

- `wf-reviewer-adversarial` —— 反例 / 边界 / 不可实现 / 遗漏前置条件
- `wf-reviewer-consistency` —— 文档间矛盾 / 契约冲突 / 语义漂移 / 未收敛

派发提示固定结构：

```
你是 <复核者名称>。以下是本轮需要复核的全部材料路径：
<逐行列出路径>

按你的定义输出发现列表与 SUMMARY 行。
```

## Step 3: 汇总与判定

1. 合并两份报告的发现列表，按 ID 去重（同一处问题被两人指出时保留依据更具体的一条）。
2. `reviewer-proposed` 类一律移入 backlog，**不计入阻断**。
3. 统计本轮 P0、P1 数量。

**通过条件**：本轮 `P0 = 0` 且 `P1 = 0`，且该轮新增意见全部 ≤ P3。

**不通过**：任一 P0/P1 存在 → 回到 `planning` 修订产物，修订后**重新跑完整一轮**（不做增量复核）。

## Step 4: P0 处置

每条 P0 必须二选一，不得悬置：

- 修改 `prd.md` / `design.md`，并在该条标注"已修"；
- 写入 `review/accepted-risks.md`，格式：

```markdown
## <ID>
- 问题：<原文>
- 接受理由：<为什么这个风险可以接受>
- 观察方式：<上线后如何发现它真的发生了>
- 接受日期：<YYYY-MM-DD>
```

**不得通过不断增加条款来解决 P0。** 若同一章节连续两轮因不同理由被标 P0，这通常说明该章节需要重写而不是打补丁——把这一点写进 `rounds.md`。

## Step 5: 落盘与轮次记录

```
.trellis/tasks/<slug>/review/
├── round-1-adversarial.md
├── round-1-consistency.md
├── round-2-...
├── rounds.md
└── accepted-risks.md
```

`rounds.md` 每轮追加一行：

```
| 轮次 | P0 | P1 | P2 | P3 | 新增 P0 来源 | 结论 |
| 1 | 3 | 4 | 6 | 2 | contract-conflict ×2, internal ×1 | 不通过 |
```

**轮次上限 5。** 到上限仍未收敛 → 停止，把 `rounds.md` 交给用户裁决。用趋势数据判断是「真盲区」还是「尺度在漂移」：若 P0 来源类别每轮都不同且互不相关，多半是后者。

## Step 6: 通过后

```bash
python .trellis/scripts/wf_status.py <task-dir> dispatching
```

然后调用 `wf-dispatch`。
