---
name: wf-init
description: 在新项目中初始化本工作流。执行 trellis init 并拉取自定义流程与 spec 骨架，探测项目画像，校验安装结果。当用户说"初始化工作流""接入 ai-workflow""新项目配置"时使用。
---

# wf-init — 新项目初始化

## 前置检查

- [ ] 目标目录是 git 仓库（否则先 `git init`）。
- [ ] 已确认 `trellis` CLI 可用：`trellis --version`。
- [ ] 已确认 Python 可调用：`python --version`（本工作流文档统一用 `python`）。

## 模式判定

初始化前先判定项目类型，两条路径的差别只在画像处理：

| 模式 | 判定依据 | 画像处理 |
| --- | --- | --- |
| 已有项目 | 仓库里已有可运行的 lint / test / build | 探测并校验命令真实可用 |
| 新项目（greenfield） | 空仓库，或没有构建系统 | 探测结果全空**是预期**，不报错；留到 Phase 0.4 填 |

## Step 1: 初始化 Trellis 并拉取自定义流程

```bash
trellis init --claude \
  --workflow rigor \
  --workflow-source gh:<user>/ai-workflow/trellis \
  --registry gh:<user>/ai-workflow/trellis/specs \
  -u <你的名字>
```

参数说明：

- `--workflow rigor` + `--workflow-source`：从本仓库的 `trellis/index.json` 拉 `workflows/rigor.md`，写入 `.trellis/workflow.md`。
- `--registry`：整目录下载 spec 骨架到 `.trellis/spec/`。

## Step 1.5: 装入状态写入助手

`task.py set-meta status` 只写 `meta.status`，面包屑不认。必须把本仓库的 `scripts/wf_status.py` 复制进项目：

```bash
cp <本仓库路径>/scripts/wf_status.py .trellis/scripts/wf_status.py
```

`trellis update` 不管理这个文件，不会被覆盖。

## Step 2: 校验流程是自定义版

```bash
grep -c "workflow-state:reviewing" .trellis/workflow.md
```

期望：输出 ≥ 2（开标签 + 闭标签）。

若为 0，说明拉取失败并回退到了 native workflow。此时**不要继续**，先排查 `--workflow-source` 路径。

## Step 3: 探测项目画像

```bash
python <本仓库路径>/scripts/detect_profile.py --root . --dry-run
```

先看输出：

- 若顶层 `commands` 四个键都有值 → 直接 `--write`。
- 若提示"检测到多个构建单元" → 说明是 monorepo，顶层命令留空是预期行为。把 stderr 中列出的各包命令复制进 `profile.commands`，或按需保留为空。
- 若提示"未探测到的命令" → 这些必须由人补齐，**不得猜测填入**。

确认后写入：

```bash
python <本仓库路径>/scripts/detect_profile.py --root . --write
```

写入会先备份为 `.trellis/config.yaml.bak`。

## Step 4: 补齐空命令

打开 `.trellis/config.yaml` 的 `profile:` 段，逐个补空项。规则：

- `test` 为空时**不允许挂机执行**——没有自动验证的长任务等于盲跑。
- `lint` / `typecheck` 为空时，检查点阶段会跳过并在报告中注明，可以接受。
- `shared_resources` 必须覆盖所有会导致并行互踩的文件（compose、环境文件、锁文件）。

**greenfield 模式**：此处四个命令都可以继续留空，直接进入 Phase 0。但 Phase 0 退出前必须填满 `lint` / `test` / `build` 三项并实测通过——这是 Phase 0 的退出条件之一，不是可选项。

## Step 4.5: greenfield 的首次任务

新建第一个任务时，状态默认是 `planning`，需要手动切到 `bootstrapping`：

```bash
python .trellis/scripts/task.py create "项目立项" --slug bootstrap --description "技术选型、架构与骨架"
python .trellis/scripts/wf_status.py .trellis/tasks/<date>-bootstrap bootstrapping
```

Phase 0 完成后切回 `planning`，再按常规流程为第一个功能建任务。

## Step 5: 接入方法论层

```bash
/plugin marketplace add <user>/ai-workflow
/plugin install ai-workflow
```

装完后确认三个技能可见：`wf-review`、`wf-dispatch`、`wf-preflight`。

## Step 6: 写项目级边界声明

在项目 `CLAUDE.md`（或 `AGENTS.md`）追加一段，明确禁用项——模型的默认倾向是"没提到就是允许"：

```markdown
## 工作流边界

- 流程权威：`.trellis/workflow.md`，状态机见其中 `[workflow-state:*]` 块。
- 规划唯一入口：`.trellis/workflow.md` 的 Phase 1，不用 Superpowers 的 brainstorming。
- 计划产物唯一来源：prd.md / design.md / dispatch.md，不用 writing-plans / executing-plans。
- 派发唯一来源：dispatch.md，不用 subagent-driven-development / dispatching-parallel-agents。
- git 由主线独占，不用 using-git-worktrees。
- 允许作为实施条款：TDD、systematic-debugging、verification-before-completion、code review。
```

## Step 7: 冒烟验证

```bash
python .trellis/scripts/task.py create "初始化验证" --slug init-check --description "验证工作流安装结果"
python .trellis/scripts/wf_status.py .trellis/tasks/<date>-init-check reviewing
python .trellis/scripts/task.py current --source
```

期望：状态变为 `reviewing`，且不再报 tag 缺失错误。确认后 `task.py archive .trellis/tasks/<date>-init-check` 掉。注意中文标题必须显式给 `--slug`，`--description` 必填。

## 完成后输出

告诉用户：

1. 初始化结果（三处校验是否通过）。
2. 画像中哪些命令为空、需要他补。
3. 下一步命令：`python .trellis/scripts/task.py create "<真实任务标题>"`。
