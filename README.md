# ai-workflow

通用 AI 开发工作流：以 Trellis 为状态底座，叠加「独立复核」与「并行派发」两个硬阶段。

适用于任意技术栈——流程层不含任何具体命令，项目事实由 `.trellis/config.yaml` 的 `profile:` 段提供。

## 解决什么

- **收敛是假象**：同一会话里 PRD"看起来收敛"，是因为作者和评审者共享同一批隐含假设。本工作流要求干净上下文的复核者找不到 P0/P1 才算通过。
- **派发失控**：文件不交集不等于可并行。共享契约、共享端口/数据库/compose 文件的改动从 diff 上看不出冲突。
- **流程无强制力**：靠 AI 自觉遵守的规则等于没有规则。本工作流把阶段写进 Trellis 的 `[workflow-state:*]` 块，每轮对话注入。

## 架构

```
流程权威  .trellis/workflow.md 的 rigor 流程   下一步做什么、能否进下一步
方法论    skills/wf-review|dispatch|preflight  这一步具体怎么做
项目事实  .trellis/config.yaml 的 profile:     命令、并发上限、冲突源
```

三者不得越界：skill 不改变状态机，profile 不含流程规则，流程文档不硬编码技术栈命令。

## 状态机

```
[已有项目] ──────────────────────────────────┐
                                             ├──▶ planning ──▶ reviewing ──▶ dispatching ──▶ in_progress ──▶ 归档
[新项目] ──▶ bootstrapping ──工具链就绪───┘          ▲            │              │
                  ▲                                  │            │              │
                  └── 复核未通过（Phase 0 内循环）    └─ P0/P1 ────┘              └─ 用户否决 ─┘
```

| 状态 | 退出条件 |
| --- | --- |
| `bootstrapping`（仅新项目） | `stack.md` 与 `design.md` 存在；lint/test/build 真实可运行并写入 `profile`；复核 0 个 P0/P1 |
| `planning` | `prd.md` 存在；复杂任务需 `design.md`；两个 context jsonl 非空 |
| `reviewing` | 某一轮 0 个 P0/P1，新增意见全部 ≤ P3 |
| `dispatching` | `dispatch.md` 落盘且用户明确批准 |
| `in_progress` | 全部并行组完成且每组检查点通过 |

## 从 0 到 1

新项目在 `planning` 之前多一个 **Phase 0（`bootstrapping`）**：

| 步骤 | 产出 |
| --- | --- |
| 0.1 技术选型 | `stack.md`——选型、理由、否决的替代方案、不可逆决策、非功能约束 |
| 0.2 架构草图 | `design.md`——模块边界、依赖方向、对外契约 |
| 0.3 骨架落地 | 目录结构 + 构建系统 + 一个能通过的测试，并提交 |
| 0.4 工具链就绪 | lint/test/build 实测可跑并写入 `profile.commands` |
| 0.5 复核 | 复用两个复核者，输入换成 stack.md + design.md + 骨架实际文件 |
| 0.6 进入规划 | 切到 `planning`，此后与已有项目完全一致 |

首轮派发默认近乎串行：构建清单（`pom.xml` / `package.json` / 工作区配置）会被多个子任务同时触碰，已列入 `forbidden_parallel`。

## 安装

```bash
# 1. Trellis 底座 + 自定义流程 + spec 骨架
trellis init --claude \
  --workflow rigor \
  --workflow-source gh:<user>/ai-workflow/trellis \
  --registry gh:<user>/ai-workflow/trellis/specs \
  -u <你的名字>

# 2. 状态写入助手（task.py 的 set-meta 不写顶层 status，必须用这个）
cp <本仓库>/scripts/wf_status.py .trellis/scripts/wf_status.py

# 3. 项目画像
python <本仓库>/scripts/detect_profile.py --root . --dry-run
python <本仓库>/scripts/detect_profile.py --root . --write

# 4. 方法论层
/plugin marketplace add <user>/ai-workflow
/plugin install ai-workflow
```

安装完成后用 `wf-init` 技能走一遍完整检查，它会校验流程版本、复制助手、探测画像并做冒烟验证。`wf-init` 会区分两种模式：已有项目校验命令可用性；新项目（greenfield）允许画像为空，直接进入 Phase 0。

## 升级

改本仓库后，在新项目重跑安装命令；已有项目用 `--append` 只补缺失文件，不覆盖本地改动。

## 允许 / 禁用的 Superpowers 技能

**允许**（作为实施条款）：`test-driven-development`、`systematic-debugging`、`verification-before-completion`、`requesting-code-review`、`receiving-code-review`。

**禁用**（与流程权威冲突）：`brainstorming`、`writing-plans`、`executing-plans`、`subagent-driven-development`、`using-git-worktrees`、`dispatching-parallel-agents`。

禁用项必须在项目 `CLAUDE.md` / `AGENTS.md` 中显式声明——「没提到就是允许」是模型的默认倾向。

## 已知限制（实测结论）

| 项 | 结论 |
| --- | --- |
| `task.py set-meta status <v>` | **写的是 `meta.status`，面包屑读顶层 `status`，完全不生效且不报错。** 必须用 `scripts/wf_status.py` |
| `task.py create` | `--description` 必填；**中文标题无法自动生成 slug**，必须显式 `--slug` |
| `task.py start` | 只在原状态为 `planning` 时翻转为 `in_progress`；从 `dispatching` 进入执行需 `start` + `wf_status.py` 两步 |
| Windows Python 命令 | `trellis init` 在本机已正确渲染为 `python`（实测），非 `python3` |
| 命令写法 | 流程文档统一用 `python`；仅提供 `python3` 的平台需全局替换 |
| `gh:<user>/<repo>/<path>` 解析 | **已实测**：`--workflow-source gh:caoguangq/ai-workflow/trellis` 与 `--registry gh:caoguangq/ai-workflow/trellis/specs` 均正常 |
| plugin marketplace 与 Trellis registry 共存 | 同一仓库同时承载两者，已实测不冲突 |
| 首次拉取超时 | Trellis 的 index 探测超时为 5s（`TIMEOUTS.INDEX_FETCH_MS`），冷启动或网络抖动时可能连续失败数次。重试 `trellis init` 即可，已下载的文件会跳过 |

## 目录

```
.claude-plugin/     plugin 与 marketplace 清单
skills/             wf-init / wf-review / wf-dispatch / wf-preflight
agents/             对抗型与一致性复核者
templates/          prd / stack / design / dispatch-plan / review-report
scripts/            detect_profile.py / wf_status.py
tests/              上述脚本的测试
trellis/            流程权威、市场索引、spec 骨架
docs/               设计文档与实现计划
```

## 开发

```bash
python -m pytest tests -q
```

要求 Python 3.9+。
