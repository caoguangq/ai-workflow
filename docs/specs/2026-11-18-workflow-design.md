# 通用 AI 开发工作流设计

- 日期：2026-11-18
- 状态：已评审，待实现
- 目标形态：独立 git 仓库 `ai-workflow`，同时作为 Claude Code plugin 与 Trellis 模板源

---

## 1. 背景与目标

现有工具各自解决一半问题：

- **Trellis** 提供持久化状态（`spec/`、`tasks/`、`workspace/`）、上下文注入 hook、任务生命周期脚本。它的 `implement` / `check` 子 agent 是执行器，但**不提供"怎么算做好"的判定标准**。
- **Superpowers** 提供方法论（TDD、systematic-debugging、verification-before-completion、code review），但**没有持久状态**，产物散落在工作区，跨会话不可恢复。

真实使用中还暴露两个 Trellis 覆盖不到的问题：

1. **派发失控**：多 agent 并行时，文件范围不交集 ≠ 可以并行。共享契约、共享运行时资源（端口、数据库、compose 文件）会造成从 diff 上看不出来的互相破坏。
2. **收敛是假象**：PRD / design 在单次会话里"看起来收敛"，是因为作者和评审者共享同一批隐含假设。换一个干净上下文的评审者，重构类任务在 3-4 轮后仍能找出 1-2 个 P0。

### 目标

1. 一套可在本人任意技术栈项目复用的工作流，硬依赖 Trellis。
2. 把「派发决策」和「独立复核」变成流程的硬阶段，由 workflow 状态机保证，不依赖 AI 自觉。
3. 方法论与技术栈解耦：流程层不含任何具体命令，项目事实由画像层供给。

### 非目标

- 不做跨模型复核（本轮选 Claude 单模型；接口预留扩展点）。
- 不做夜间自动调度器 / cron。
- 不修改 Trellis 的 `task.py` 或任何 hook 脚本。
- 不接管 Superpowers 的 `brainstorming` / `writing-plans` / `executing-plans` / `subagent-driven-development`。

---

## 2. 设计依据（已验证的机制事实）

以下结论来自对 `@mindfoldhq/trellis@0.6.17` 源码的核对，不是推测：

| 事实 | 出处 | 设计含义 |
| --- | --- | --- |
| 面包屑由 `task.json` 的 `status` 字符串决定，在 workflow.md 中查找 `[workflow-state:<status>]` 块；未找到则退化通用提示 | `inject-workflow-state.py:192-231, 373-380` | 新增流程状态**零成本**，只需在 workflow.md 加对应 tag 块 |
| 状态 tag 字符集为 `[A-Za-z0-9_-]+` | `workflow.md:696` | `reviewing` / `dispatching` 合法 |
| `task.py set-meta <dir> <key> <value>` 写入的是嵌套的 `meta.<key>`，**不是顶层字段** | `task.py:719`；E2E 实测 `meta.status` | 不能用它切状态；需要自带写入脚本 `wf_status.py` |
| `task.py start` **仅在 status 为 `planning` 时**才翻转为 `in_progress` | `task.py:112-114` | 自定义状态机必须显式写顶层 `status`，不能依赖 `start` 的翻转 |
| `task.py create` 要求 `--description`，且中文标题无法自动生成 slug | E2E 实测 | 建任务必须显式给 `--slug` 与 `--description` |
| `task.py start` 在 `implement.jsonl` / `check.jsonl` 为空时拒绝启动 | `task.py` / `workflow.md:54-58` | 这是天然的规划完成闸门，直接复用 |
| 非 `native` 的 workflow.md 从 `.template-hashes.json` 中移除，`trellis update` 不覆盖 | `workflow-resolver.js:18-28`, `commands/workflow.js` | 自定义流程可长期存活 |
| `-r <source>` 无 index.json 时整目录下载到 `.trellis/spec/` | `template-fetcher.js:907-927` | spec 骨架可分发 |
| `--workflow-source` 要求该 source 根有 `index.json`，条目 `type: "workflow"` | `workflow-resolver.js:50-90` | 自定义 workflow 可分发 |
| `-t <id>` 目前仅支持 `type: "spec"` | `template-fetcher.js:837-842` | 不能靠 `-t` 分发技能或 agent |

---

## 3. 总体架构

三层职责，边界不可混淆：

```
流程权威（rigor.md）      回答「下一步做什么、能不能进下一步」
    │
    ├─ 技能（skills/）      回答「这一步怎么做」
    │
    └─ 项目画像（profile）  回答「这个项目的具体事实是什么」
```

- **唯一流程权威**：`rigor.md`。写在 `.trellis/workflow.md`，通过面包屑每轮提醒。
- **技能只做步骤执行**，不声称下一步是什么，不改变状态机。
- **Superpowers 仅作为条款来源**，其流程性技能禁用（见 §8）。

### 仓库结构

```
ai-workflow/
├── .claude-plugin/
│   ├── plugin.json
│   └── marketplace.json
├── skills/
│   ├── wf-dispatch/SKILL.md
│   ├── wf-review/SKILL.md
│   └── wf-preflight/SKILL.md
├── agents/
│   ├── wf-reviewer-adversarial.md
│   └── wf-reviewer-consistency.md
├── templates/
│   ├── prd.md
│   ├── design.md
│   ├── dispatch-plan.md
│   └── review-report.md
├── trellis/
│   ├── index.json
│   ├── workflows/rigor.md
│   └── specs/
│       ├── generic/
│       ├── guides/
│       └── stacks/
└── README.md
```

一个仓库两个分发面：Claude Code 从 `.claude-plugin/` 安装 plugin；Trellis 从 `trellis/` 拉 workflow 与 spec。

---

## 4. 流程状态机（`rigor.md`）

```
planning ──规划产物齐备──▶ reviewing ──0 个 P0/P1──▶ dispatching ──用户批准──▶ in_progress ──▶ 归档
   ▲                          │                          │                        │
   └──────── P0/P1 打回 ───────┘                          └────── 用户否决 ─────────┘
```

| 状态 | 阶段内容 | 退出条件（硬性） |
| --- | --- | --- |
| `planning` | 1.0 建任务 → 1.1 需求探索 → 1.2 调研 → 1.3 登记上下文清单 | `prd.md` 存在；复杂任务需 `design.md`；`implement.jsonl` 与 `check.jsonl` 均非空 |
| `reviewing` | 1.4 独立复核循环 | 某一轮 0 个 P0/P1，且新增意见全部 ≤ P3 |
| `dispatching` | 1.5 派发计划 | `dispatch.md` 落盘且用户明确批准 |
| `in_progress` | 2.1 按并行组执行 → 2.2 每组完成后立即检查并提交 | 全部组完成且每组检查通过 |
| `in_progress`（收尾） | 3.1 复盘 → 3.2 spec 更新 → 3.3 提交 → 3.4 归档 | 任务归档且 journal 写入 |

### 任务分流

全流程对每个改动都跑一遍会让工作流变成负担，因此分两档：

| 档位 | 条件 | 路径 |
| --- | --- | --- |
| 轻量 | 单文件、无接口契约变更、`spec/` 中无对应领域规则 | `planning` → `in_progress`（跳过 `reviewing` / `dispatching`） |
| 标准 | 下列任一命中 | 全流程 |

判定为标准的任一条件：

1. 跨包或跨层改动（后端 ↔ 前端、service ↔ controller、公共库 ↔ 应用）。
2. 改动接口契约：API schema、DTO、表结构、前端类型定义、i18n 词条。
3. 改动领域规则：变更涉及 `spec/` 中已有条目描述的行为。

轻量档必须在 `prd.md` 顶部写 `tier: light`，并一句话说明为什么满足轻量条件。**拿不准时按标准档走**——多花的是时间，少走的是返工。

「复杂任务」在本设计中统一定义为：**存在 `design.md` 的任务**。此时复核必须同时覆盖 `prd.md` 与 `design.md`。

### 状态切换命令

```bash
# 进入复核
python .trellis/scripts/wf_status.py <task-dir> reviewing

# 复核通过，进入派发设计
python .trellis/scripts/wf_status.py <task-dir> dispatching

# 用户批准派发计划后：先激活指针，再显式翻转状态
python .trellis/scripts/task.py start <task-dir>
python .trellis/scripts/wf_status.py <task-dir> in_progress
```

**必须用 `wf_status.py`**：`task.py set-meta` 只写 `meta.status`，面包屑读的是顶层 `status`，写了不生效也不报错；`task.py start` 只在原状态为 `planning` 时翻转，此处不满足。`wf_status.py` 同时校验 workflow.md 中存在对应 state tag，挡掉 tag 缺失导致的静默退化。

### workflow.md 需要的 tag 块

`[workflow-state:planning]`、`[workflow-state:reviewing]`、`[workflow-state:dispatching]`、`[workflow-state:in_progress]`、`[workflow-state:no_task]`、`[workflow-state:task_error]`。

块正文需写明：本阶段允许做什么、禁止做什么、退出条件、下一步命令。逐轮提醒是这套机制强制力的唯一来源。

---

## 5. 复核层

### 5.1 两个 reviewer

| Reviewer | 只找 | 明确不找 |
| --- | --- | --- |
| `wf-reviewer-adversarial` | 反例、边界条件、不可实现的描述、遗漏的前置条件 | 措辞、内部一致性 |
| `wf-reviewer-consistency` | PRD ↔ design 矛盾、与代码/接口契约冲突、语义漂移、术语不一致 | 新需求 |

两者并行派发，上下文互相隔离，且**互不可见对方的报告**。

### 5.2 干净上下文规则（硬约束）

**必须提供**（由主 agent 在派发提示中显式列出路径）：

- `prd.md`、`design.md`
- 本次涉及文件的真实内容
- 相关接口契约：API schema、DTO、表结构、前端类型定义
- `.trellis/spec/` 中适用条目
- 项目 `AGENTS.md` / `CLAUDE.md`

**必须不提供**：

- 作者的推理过程与自我辩护（"我已经考虑过 X，所以 Y 没问题"）
- 上一轮复核报告（防止锚定）
- 会话历史摘要

判定标准：**带全部事实，剥掉全部主张。**

### 5.3 报告格式

```markdown
[ID] R3-A-02
[定位] prd.md §4.2 第 3 条
[分类] internal-contradiction | contract-conflict | spec-conflict | reviewer-proposed
[严重度] P0 | P1 | P2 | P3
[置信度] 高 | 中 | 低
[问题] 一句话陈述
[依据] 引用的代码 / 契约 / spec 原文
[建议] 可执行的最小修改
```

### 5.4 判停规则

- **通过**：某一轮 0 个 P0/P1，且该轮新增意见全部 ≤ P3。
- **`reviewer-proposed` 永不阻断**：一律进 backlog。这是防止评审者发明需求、把 PRD 撑成互相打补丁的缝合怪。
- **P0 只能二选一**：修改 PRD/design，或在 `accepted-risks.md` 显式记录「已知并接受 + 理由」。
- **上限 5 轮**。到上限仍未收敛 → 停止，交人工裁决。每轮记录 P0/P1 数量到 `review/rounds.md`，用趋势数据区分「真盲区」与「尺子在漂」。

### 5.5 产物

```
.trellis/tasks/<slug>/review/
├── round-1-adversarial.md
├── round-1-consistency.md
├── round-2-adversarial.md
├── ...
├── rounds.md          # 每轮 P0/P1 计数与趋势
└── accepted-risks.md  # 显式接受的风险
```

---

## 6. 派发层

### 6.1 三层冲突判定

任一层命中，即**不可并行**：

| 层 | 判定方法 | 实例 |
| --- | --- | --- |
| 文件层 | 变更文件集合有交集 | 同改一个 service |
| 契约层 | 同改一个 DTO / 表结构 / API schema / 前端类型定义 / i18n 词条 | 后端 DTO 与前端类型 |
| 运行时层 | 共用端口、数据库、dev server、build 缓存、compose 文件、环境文件 | `docker-compose*.yml`、`.env.prod` |

### 6.2 并行上限

默认 `max_parallel: 3`，记录在项目画像中。瓶颈不是机器，是人复核 diff 的注意力。

### 6.3 派发计划

必须落盘到 `.trellis/tasks/<slug>/dispatch.md`，格式：

```markdown
# Dispatch Plan — <task>

## 变更面
- packages: [...]
- files: [...]

## 冲突矩阵
| 层 | 命中项 | 结论 |
| --- | --- | --- |

## 并行组
### Group 1（并行）
- 目标：
- 文件：
- 放行依据：文件层不交集；契约层无共享；运行时层无共享

### Group 2（串行于 Group 1）
- 原因：与 Group 1 共享 <契约/文件>

## 检查点
- Group 1 完成 → check + commit
- Group 2 完成 → check + commit

## git 策略
- 并行组内 agent 禁止一切 git 操作
- 主线在每组完成后提交
```

### 6.4 执行铁律

1. 并行组内 agent **禁止任何 git 操作**（`add` / `commit` / `checkout` / `stash` / `reset`）。git 只由主线执行。
2. 每组完成后**立即**检查并提交，形成可独立回滚的检查点。禁止全部跑完再一次性提交。
3. 任一检查点失败 → 停止后续组，回到 `reviewing` 或 `planning`，不得"先跑完再修"。

---

## 7. 项目画像

写入 `.trellis/config.yaml` 的 `profile:` 段。工作流与技能**只读这里，不硬编码任何命令**。

```yaml
profile:
  commands:
    lint: ""
    typecheck: ""
    test: ""
    build: ""
  concurrency:
    max_parallel: 3
  shared_resources:
    - docker-compose.yml
    - docker-compose.prod.yml
    - .env.prod
  forbidden_parallel:
    - src/main/resources/db/migration/
```

规则：

- 初始化时自动探测 `pom.xml` / `package.json` / `turbo.json` / `Makefile` / `build.gradle`。
- **探测不到就留空，不猜**。命令为空时，流程在该步骤停下来提示用户补齐。
- `forbidden_parallel` 中的路径任何情况下不得进入并行组。

---

## 8. 与 Superpowers 的边界

| Superpowers 技能 | 处置 |
| --- | --- |
| `test-driven-development` | **保留**，作为 `in_progress` 阶段的实施条款 |
| `systematic-debugging` | **保留**，用于检查点失败后的诊断 |
| `verification-before-completion` | **保留**，"完成"必须附带命令输出与测试证据 |
| `requesting-code-review` / `receiving-code-review` | **保留**，用于组间检查 |
| `brainstorming` | **禁用**，由 `planning` 阶段与 `wf` 流程接管 |
| `writing-plans` / `executing-plans` | **禁用**，计划产物唯一来源是 `prd.md` / `design.md` / `dispatch.md` |
| `subagent-driven-development` | **禁用**，派发唯一来源是 `dispatch.md` |
| `using-git-worktrees` | **禁用**，git 由主线独占 |
| `dispatching-parallel-agents` | **禁用**，并行决策唯一来源是 §6.1 |

禁用项需在插件的 skill 描述与项目 `CLAUDE.md` 中同时声明，理由：模型对"未提及即允许"的默认倾向很强。

---

## 9. spec 骨架

```
.trellis/spec/
├── generic/            # 栈无关
│   ├── error-handling/
│   ├── logging/
│   ├── configuration/
│   ├── testing-strategy/
│   └── commit-convention/
├── guides/             # 跨包思考指南（Trellis 原生约定）
└── stacks/             # 按需启用
    ├── spring-boot/
    ├── vue/
    └── node/
```

每条规范必须是 **code-spec**：可执行契约（签名、字段、边界行为、错误码），不是原则性文字。理由：`check` 子 agent 只能验证可执行的东西。

---

## 10. 安装与升级

```bash
# 新项目
trellis init --claude --workflow rigor \
  --workflow-source gh:<user>/ai-workflow/trellis \
  --registry gh:<user>/ai-workflow/trellis/specs -u <name>

# Claude Code plugin
/plugin marketplace add <user>/ai-workflow
/plugin install ai-workflow
```

升级：修改仓库后重跑上述命令；补缺失文件用 `--append`，不覆盖本地已改内容。

---

## 11. 失败模式与对策

| 失败模式 | 对策 |
| --- | --- |
| 评审者发明需求，PRD 无限膨胀 | `reviewer-proposed` 分类永不阻断，进 backlog |
| 复核不收敛 | 上限 5 轮 + `rounds.md` 趋势数据 + 人工裁决 |
| 并行 agent 互相覆盖 | 三层冲突判定 + 组内禁 git + 组间检查点 |
| 挂机跑整晚产出不可解的大 diff | `wf-preflight` 单向审 + 分组 commit |
| `trellis update` 覆盖自定义流程 | 已验证：非 native workflow 不受影响 |
| 自定义状态不翻车 | `wf_status.py` 写顶层 `status` 并校验 tag 存在；`start` 仅负责激活指针 |
| 命令探测出错 | 探测不到留空，流程停下提示，不猜 |

---

## 12. 实现前需实测的假设

1. `gh:<user>/<repo>/<path>` 形式能否同时用于 `--workflow-source`（需 `index.json` 在该路径根）与 `--registry`（整目录下载）。
2. 同一仓库同时作为 Claude Code plugin marketplace 与 Trellis registry，安装时是否互不干扰。
3. Windows 下 Python 命令探测：目标机器 `python3` 不存在、仅有 `python`，`init` 是否正确写入 `{{PYTHON_CMD}}`。
4. ~~`set-meta status` 写入后面包屑是否识别~~ —— E2E 已实测：**不识别**，且不报错。已改用 `scripts/wf_status.py` 写顶层字段。
