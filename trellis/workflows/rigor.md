# Development Workflow (Rigor)

> 本文件是流程的**唯一权威**。它回答「下一步做什么、能不能进下一步」。
> 具体做法由 skill 回答；项目事实由 `.trellis/config.yaml` 的 `profile:` 段提供。
> 本文件为非 native workflow，`trellis update` 不会覆盖。
> 命令统一使用 `python`；若平台只有 `python3`，全局替换即可。

---

## 0. 三层职责

| 层 | 位置 | 只回答 |
| --- | --- | --- |
| 流程权威 | 本文件 | 下一步做什么、能否进下一步 |
| 方法论 | `.claude/skills/wf-*` | 这一步具体怎么做 |
| 项目事实 | `profile:` 段 | 这个项目的命令、并发上限、冲突源 |

任何一层不得越界：skill 不得改变状态机，profile 不得包含流程规则，本文件不得硬编码任何技术栈命令。

---

## 1. 核心原则

1. **先规划后实现** —— 规划产物通过复核前，不得改动业务代码。
2. **规范注入而非记忆** —— 规则从 `spec/` 与 `profile:` 读取，不靠会话记忆。
3. **一切落盘** —— 调研、决策、复核结论都写入任务目录；会话会被压缩，文件不会。
4. **一次一个任务** —— 同一时刻只有一个活跃任务。
5. **收敛必须证伪** —— 「看起来对了」不算收敛；干净上下文复核者找不到 P0/P1 才算。

---

## 2. 状态机

```
[已有项目] ───────────────────────────────────────────────┐
                                                          ├──▶ planning ──▶ reviewing ──▶ dispatching ──▶ in_progress ──▶ 归档
[新项目] ──▶ bootstrapping ──工具链就绪 + 复核通过───────┘         ▲            │              │
                    ▲                                              │            │              │
                    └──── 复核未通过（Phase 0 内循环）              └─ P0/P1 ────┘              └─ 用户否决 ─┘
```

| 状态 | 含义 | 退出条件 |
| --- | --- | --- |
| `bootstrapping` | **仅新项目**。技术选型、架构、骨架、工具链 | `stack.md` 与 `design.md` 存在；`profile.commands` 的 lint/test/build 全部可真实运行；复核 0 个 P0/P1 |
| `planning` | 需求探索与规划 | `prd.md` 存在；复杂任务需 `design.md`；`implement.jsonl` 与 `check.jsonl` 均非空 |
| `reviewing` | 独立复核循环 | 某一轮 0 个 P0/P1，且新增意见全部 ≤ P3 |
| `dispatching` | 派发计划待批 | `dispatch.md` 落盘且用户明确批准 |
| `in_progress` | 执行与收尾 | 全部并行组完成，每组检查通过 |

**两种入口**：

- **已有项目**：`create` 后状态即 `planning`，直接进 Phase 1。
- **新项目**：`create` 后先 `wf_status.py <task-dir> bootstrapping`，走完 Phase 0 再进入 Phase 1。

判断依据：仓库里已有可运行的 lint/test/build 命令 → 已有项目；连构建系统都没有 → 新项目。

状态写入方式：

```bash
python .trellis/scripts/wf_status.py <task-dir> <状态名>
python .trellis/scripts/task.py current --source    # 查看当前活跃任务与状态
```

**不要用 `task.py set-meta status`**：它写入的是 `meta.status`，而面包屑读的是顶层 `status` 字段，写了也不会生效，且不报错。`wf_status.py` 同时校验 workflow.md 中存在对应的 state tag，挡掉"tag 缺失导致面包屑静默退化"这一类故障。

**注意**：`task.py start` 只在原状态为 `planning` 时才翻转为 `in_progress`。从 `dispatching` 进入执行时必须两步走：

```bash
python .trellis/scripts/task.py start <task-dir>            # 只负责激活任务指针
python .trellis/scripts/wf_status.py <task-dir> in_progress # 显式翻转状态
```

---

## 3. Phase Index

面包屑由 `task.json` 的 `status` 值决定，逐轮注入。以下块正文必须简短——它们每轮都会占用上下文。

[workflow-state:no_task]
当前没有活跃任务。
允许：新建任务、判定任务档位。
禁止：改动业务代码。
下一步：`python .trellis/scripts/task.py create "<标题>" --slug <slug> --description "<交付什么>"`
随后按「任务分流」判定 tier，写入 prd.md 顶部。
[/workflow-state:no_task]

[workflow-state:task_error]
活跃任务记录不可读。
允许：修复 `.trellis/tasks/<dir>/task.json`。
禁止：任何其他操作。
下一步：检查 JSON 合法性后重新执行 `task.py current`。
[/workflow-state:task_error]

[workflow-state:bootstrapping]
阶段：立项（仅新项目）。目标是让仓库具备可运行的工程基础。
允许：技术选型；写 stack.md / design.md；搭目录与构建系统；跑通一行能过的测试；补 profile.commands。
禁止：编写业务功能代码；跳过工具链直接进入需求规划。
退出条件：stack.md 与 design.md 存在；lint/test/build 三条命令真实可运行并已写入 profile；复核 0 个 P0/P1。
**本阶段 `profile.commands` 为空是合法的**，但退出前必须填满 lint/test/build 三项。
下一步：退出条件满足后执行
`python .trellis/scripts/wf_status.py <task-dir> planning`，然后进入 Phase 1。
复核流程见 Phase 0.5，复用 wf-review 技能。
[/workflow-state:bootstrapping]

[workflow-state:planning]
阶段：规划。目标是把需求变成可复核的产物。
允许：写 prd.md / design.md；调研；用 `add-context` 登记 implement.jsonl 与 check.jsonl。
禁止：改动业务代码；`task.py start`。
退出条件：prd.md 存在；复杂任务需 design.md；两个 jsonl 均非空。
下一步：产物齐备后执行
`python .trellis/scripts/wf_status.py <task-dir> reviewing`，然后调用 wf-review 技能。
[/workflow-state:planning]

[workflow-state:reviewing]
阶段：独立复核。收敛必须由干净上下文的复核者证伪，不能自证。
允许：并行派发 wf-reviewer-adversarial 与 wf-reviewer-consistency；按报告修订产物。
禁止：改动业务代码；跳过复核直接派发；让复核者看到上一轮报告。
通过条件：某一轮 0 个 P0/P1，且新增意见全部 ≤ P3。
下一步：通过后执行
`python .trellis/scripts/wf_status.py <task-dir> dispatching`，然后调用 wf-dispatch 技能。
轮次上限 5；超限停止并交人工裁决。
[/workflow-state:reviewing]

[workflow-state:dispatching]
阶段：派发设计。目标是产出一份用户可批准的执行顺序。
允许：写 dispatch.md；分析冲突矩阵；等待用户批准。
禁止：派发执行 agent；改动业务代码。
退出条件：dispatch.md 落盘，且用户明确批准。
下一步：批准后依次执行
`python .trellis/scripts/task.py start <task-dir>`
`python .trellis/scripts/wf_status.py <task-dir> in_progress`
[/workflow-state:dispatching]

[workflow-state:in_progress]
阶段：执行与收尾。
允许：按 dispatch.md 的并行组执行；每组完成后立即检查并提交。
禁止：跨组并行；组内 agent 执行任何 git 操作；跳过检查点。
铁律：组内 agent 只改文件，git 由主线独占。
下一步：每组完成后运行 profile.commands 中的 lint/test，通过则 commit；
全部组完成进入 Phase 3（复盘 → spec 更新 → 提交 → 归档）。
[/workflow-state:in_progress]

---

## 4. 任务分流

全流程对每个改动都跑一遍会变成负担，因此分两档。

| 档位 | 条件 | 路径 |
| --- | --- | --- |
| 轻量 | 单文件、无接口契约变更、`spec/` 中无对应领域规则 | `planning` → `in_progress`（跳过 reviewing / dispatching） |
| 标准 | 下列任一命中 | 全流程 |

判定为标准档的任一条件：

1. 跨包或跨层改动（后端 ↔ 前端、service ↔ controller、公共库 ↔ 应用）。
2. 改动接口契约：API schema、DTO、表结构、前端类型定义、i18n 词条。
3. 改动领域规则：涉及 `spec/` 中已有条目描述的行为。

轻量档必须在 `prd.md` 顶部写 `tier: light` 并一句话说明理由。**拿不准时按标准档走。**

「复杂任务」在本工作流中统一定义为：**存在 `design.md` 的任务**。

**新项目例外**：Phase 0（`bootstrapping`）期间不适用分流——立项阶段本身就是全量流程，且必须复核。Phase 0 完成后，后续任务按常规两档判定。

---

## 5. Phase 0: Bootstrap（仅新项目）

从 0 到 1 时，最先要解决的不是需求，而是「什么栈、什么骨架、怎么验证」。跳过这一步直接进 Phase 1，会得到一份无法验证的 PRD。

判断是否走本阶段：仓库里已有可运行的 lint/test/build → 跳过，直接 Phase 1；否则必须走完。

### 0.1 技术选型 `[required · once]`

产出 `stack.md`（用 `templates/stack.md`）。必须包含：

- 每一项选型（语言、框架、数据库、构建工具、测试框架）及其理由。
- **至少一个被认真考虑后否决的替代方案**，写明否决理由。空着视为未完成。
- 非功能约束：预期的并发量、数据规模、部署形态、团队熟悉度。
- 不可逆决策单独标出（例如数据库类型、API 风格）——这些错了代价最高。

先查证再提问：库的具体版本与兼容性从官方文档或仓库确认，不要凭记忆。

### 0.2 架构草图 `[required · once]`

产出 `design.md`。重点不是细节，而是**边界**：

- 模块划分与各自职责，模块之间允许的依赖方向。
- 核心领域对象与它们的生命周期。
- 对外契约的形态（API 风格、数据结构、错误约定）。
- 哪些决策留待后续任务再定，以及为什么现在不定。

### 0.3 骨架落地 `[required · once]`

目标：让仓库从"空"变成"能跑"。

- 目录结构落到磁盘。
- 构建系统可用，能产出可运行产物。
- 一行能通过的测试（哪怕只断言 `true`）——它的作用是证明测试链路是通的。
- 一条 lint 命令可运行。

骨架本身是一个可提交的检查点：**提交后再进入下一步**，这样后续所有改动都有回滚点。

### 0.4 工具链就绪 `[required · once]`

把真实可用的命令写入 `.trellis/config.yaml` 的 `profile.commands`：

- `lint` / `test` / `build` **三项必须填满且实测能跑通**。
- `typecheck` 没有就留空，合法。
- 同时填 `shared_resources`（compose、环境文件、锁文件）与 `forbidden_parallel`（迁移目录、构建清单）。

实测方式：逐条在终端跑一遍，确认退出码为 0。**没跑过的命令不算填好。**

### 0.5 复核 `[required · once 起]`

调用 `wf-review` 技能，但输入与 Phase 1 不同：

- 输入：`stack.md`、`design.md`、骨架的实际文件清单、`profile.commands` 的实际输出。
- 复核重点：选型是否自相矛盾、模块边界是否闭合、非功能约束是否被选型满足、不可逆决策是否被论证。
- 判停规则与 Phase 1 相同（0 个 P0/P1，上限 5 轮）。

复核者在这阶段找不到代码可对照，所以**必须把选型的理由与限制一起给它**——否则它只能凭通用直觉判断。

### 0.6 进入规划

```bash
python .trellis/scripts/wf_status.py <task-dir> planning
```

此后与已有项目走完全相同的流程。

---

## 6. Phase 1: Plan

### 1.0 建任务 `[required · once]`

```bash
python .trellis/scripts/task.py create "<标题>" --slug <slug> --description "<交付什么>"
```

`--description` 必填（空描述的任务在归档时会被拒绝）。**中文标题无法自动生成 slug**，必须显式给 `--slug`，用英文短横线格式。

只建不激活。`start` 会切状态，留到 1.5 之后。

### 1.1 需求探索 `[required · repeatable]`

- 一次只问一个最高价值的问题。
- **问之前必须先查代码**：仓库能回答的事实不准问用户。
- 只问产品意图、范围、取舍、风险容忍度、验收行为。
- 需求澄清结束时，用一段话复述最终理解，等待用户确认。

产物：`prd.md`（用 `templates/prd.md` 的结构）。验收标准必须可测，每条对应一个检查命令或人工判定动作。

### 1.2 调研 `[optional · repeatable]`

需要外部知识（API 行为、库版本、历史实现）时派 `trellis-research`，产物放 `research/`。

### 1.3 登记上下文 `[required · once]`

把本次要用到的 spec 与调研文件登记进两个清单，子 agent 靠它拿上下文：

```bash
python .trellis/scripts/task.py add-context <task-dir> implement <文件路径> "<为什么需要>"
python .trellis/scripts/task.py add-context <task-dir> check <文件路径> "<为什么需要>"
```

清单为空时 `task.py start` 会拒绝启动——这是规划完成的硬闸门。

### 1.4 复核 `[required · once 起]`

调用 `wf-review` 技能。状态切到 `reviewing`。规则见技能文档：两个隔离复核者、`reviewer-proposed` 进 backlog、P0 二选一、上限 5 轮。

产物：`review/round-N-<reviewer>.md`、`review/rounds.md`、`review/accepted-risks.md`。

### 1.5 派发设计 `[required · once]`

调用 `wf-dispatch` 技能。状态切到 `dispatching`。产出 `dispatch.md` 并等待用户批准。

**用户批准前不得派发任何执行 agent。**

---

## 7. Phase 2: Execute

### 2.1 按组执行 `[required · repeatable]`

严格按 `dispatch.md` 的分组顺序：

- 组内可并发派发。
- **组内 agent 禁止任何 git 操作**（`add` / `commit` / `checkout` / `stash` / `reset` / `branch`）。
- 组内 agent 的上下文由主 agent 显式给出：任务目标、涉及文件、相关 spec 条目。

### 2.2 每组后检查 `[required · repeatable]`

每组完成立即执行：

1. `git diff --name-only` 核对实际改动面是否符合派发计划。
2. 跑 `profile.commands.lint`、`profile.commands.typecheck`、`profile.commands.test`（为空的项跳过并在报告中注明）。
3. 通过则主线提交，形成检查点。

### 2.3 失败处理

任一检查点失败：

- 停止后续组，**不得"先跑完再修"**。
- 需要定位根因时用 systematic-debugging 条款。
- 属于规划缺陷则回 `planning`；属于实现缺陷则修后重跑该组。

---

## 8. Phase 3: Finish

### 3.1 复盘 `[optional]`

若本次修过 bug，调用 `trellis-break-loop` 做一次归类分析。

### 3.2 spec 更新 `[required · once]`

调用 `trellis-update-spec`，把本次学到的东西写成 **code-spec**（签名、字段、边界行为、错误码），不是原则性文字。

### 3.3 提交 `[required · once]`

```bash
git status --porcelain
git add <本次改动>
git commit -m "<type>: <描述>"
```

### 3.4 归档 `[required · once]`

调用 `/trellis:finish-work`：归档任务、写 journal。

---

## 9. 项目画像

工作流只读 `profile:` 段，**不得硬编码任何命令**。

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

- 命令为空表示未探测到：流程在该步骤停下，提示用户补齐，**不得猜测**。
- `shared_resources` 与 `forbidden_parallel` 中的条目永远不得进入并行组。

---

## 10. 与 Superpowers 的边界

**允许**（作为实施条款）：

| 技能 | 用在 |
| --- | --- |
| `test-driven-development` | 2.1 实施 |
| `systematic-debugging` | 2.3 失败诊断 |
| `verification-before-completion` | 2.2 检查点的完成判定 |
| `requesting-code-review` / `receiving-code-review` | 组间检查 |

**禁用**（与流程权威冲突）：

| 技能 | 禁用理由 |
| --- | --- |
| `brainstorming` | 规划唯一入口是 1.1 与本文件 |
| `writing-plans` / `executing-plans` | 计划产物唯一来源是 prd.md / design.md / dispatch.md |
| `subagent-driven-development` | 派发唯一来源是 dispatch.md |
| `using-git-worktrees` | git 由主线独占，worktree 会破坏这一点 |
| `dispatching-parallel-agents` | 并行决策唯一来源是本文件 §6 与 wf-dispatch |

「没提到就是允许」是模型的默认倾向，因此禁用项必须显式列出，不能靠省略。

---

## 11. 规则与护栏

- 任务创建批准 ≠ 实现批准。实现必须等用户名明确批准 `dispatch.md`。
- 复核者看不到作者推理、看不到上一轮报告、看不到会话摘要。
- 每条 P0 必须二选一：修改产物，或写入 `accepted-risks.md` 并说明理由。
- `reviewer-proposed` 类意见永不阻断，进 backlog。
- 并行组内一律禁止 git；检查点提交只由主线执行。
- 命令、并发上限、冲突源一律来自 `profile:`，不得出现在本文件的命令示例之外。
