---
name: wf-dispatch
description: 在规划复核通过后设计执行派发顺序。按文件/契约/运行时三层判定哪些改动可并行、哪些必须串行，生成 dispatch.md 并等待用户批准。当用户说"派发""并行做""开始执行"时使用。
---

# wf-dispatch — 派发设计

流程权威是 `.trellis/workflow.md` 的 `[workflow-state:dispatching]` 块。本技能只说明**这一步怎么做**。

## 前置检查

- [ ] 复核已通过（`review/rounds.md` 最后一轮 P0=0 且 P1=0）。
- [ ] `task.json` 的 `status` 已是 `dispatching`。

## Step 1: 确定变更面

```bash
git status --porcelain
git diff --name-only HEAD
```

按包/模块分组列出现有改动与计划改动。计划改动来自 `prd.md` 与 `design.md`，不是来自现有 diff。

## Step 2: 三层冲突判定

任一层命中，两个改动**不可并行**。

### 文件层

两个子任务的变更文件集合有交集 → 串行。

### 契约层

两个子任务改同一个「契约实体」的任一端 → 串行。契约实体包括：

- API schema / DTO / 请求响应结构
- 表结构、迁移脚本、索引
- 前端类型定义与后端结构的对应关系
- i18n 词条的键
- 公共库导出

即使两端在不同文件、甚至不同包，也算冲突。

### 运行时层

两个子任务共用任一资源 → 串行：

- 端口、dev server、数据库实例、缓存实例
- 构建缓存、包管理器锁文件
- `profile.shared_resources` 中列出的任何文件
- `profile.forbidden_parallel` 中列出的任何路径（任何情况下不得并行）

```bash
# 读取项目画像
python -c "import re,sys; s=open('.trellis/config.yaml',encoding='utf-8').read(); i=s.find('profile:'); print(s[i:i+1200] if i>=0 else 'PROFILE MISSING')"
```

画像缺失时**停止**，先让用户补齐——不要在不知道冲突源的情况下设计并行。

### greenfield 首轮

新项目在 Phase 0 之后的第一轮派发，默认**接近串行**，原因：

- 构建清单（`pom.xml` / `package.json` / `pnpm-workspace.yaml` / `turbo.json`）几乎每个子任务都会碰，`detect_profile.py` 已把它们放进 `forbidden_parallel`。
- 领域模型尚未定型，两个并行子任务很容易各自发明一套不一致的抽象。
- 让第一组先跑通「实现 → 检查 → 提交」的完整链路，比多并行两个任务更有价值。

只有当子任务之间既无共享构建清单、也无共享领域模型时，才允许并行。

## Step 3: 生成 dispatch.md

写入 `.trellis/tasks/<slug>/dispatch.md`，结构固定：

```markdown
# Dispatch Plan — <task>

## 变更面
- packages: [...]
- planned files: [...]

## 冲突矩阵
| 层 | 命中项 | 涉及子任务 | 结论 |
| --- | --- | --- | --- |

## 并行组
### Group 1（并行）
- 子任务：
- 涉及文件：
- 放行依据：文件层不交集；契约层无共享；运行时层无共享

### Group 2（串行于 Group 1）
- 子任务：
- 阻塞原因：与 Group 1 共享 <具体契约/文件/资源>

## 检查点
- Group 1 完成 → 检查 + 提交
- Group 2 完成 → 检查 + 提交

## git 策略
- 组内 agent 禁止一切 git 操作
- 主线在每组完成后提交
```

## Step 4: 并行上限

读取 `profile.concurrency.max_parallel`（默认 3）。超出的子任务顺延到下一组，不得压缩上限。

分组原则：**先做无依赖的、契约定义方先于契约消费方**。定义方（表结构、DTO、类型）先落地并提交，消费方再并行——这能把大部分契约层冲突消掉。

## Step 5: 等待用户批准

把 `dispatch.md` 的内容呈现给用户，明确请求批准：

> 派发计划已写入 `<path>`。请确认：① 分组顺序 ② 并行组的放行依据 ③ 检查点划分。批准后我再开始执行。

**用户明确批准前不得派发任何执行 agent。**

## Step 6: 批准后激活

```bash
python .trellis/scripts/task.py start <task-dir>
python .trellis/scripts/wf_status.py <task-dir> in_progress
```

## 执行阶段的铁律（提示，不在本技能内执行）

1. 组内 agent 禁止任何 git 操作。
2. 每组完成后立即跑检查并提交，形成可独立回滚的检查点。
3. 任一检查点失败 → 停止后续组，不得"先跑完再修"。
4. 实际改动面与 `dispatch.md` 不符时，停止并重新做冲突判定。
