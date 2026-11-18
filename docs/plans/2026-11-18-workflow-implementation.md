# 通用 AI 工作流实现计划

> **执行方式：** 本计划按顺序逐任务执行，每步用 `- [ ]` 勾选跟踪。任务边界处停下来让我确认。

**目标：** 建成 `ai-workflow` 仓库——同时作为 Claude Code plugin 与 Trellis 模板源分发，为任意技术栈项目提供「规划 → 复核 → 派发 → 执行」的硬流程。

**架构：** 流程权威是自定义的 `trellis/workflows/rigor.md`（替换 Trellis 的 native workflow）；方法论细节放在三个 skill 里；复核者是两个上下文隔离的 subagent；项目事实由 `.trellis/config.yaml` 的 `profile:` 段供给。不改 Trellis 的任何脚本或 hook。

**技术栈：** Markdown（skill / agent / workflow）、JSON（plugin / marketplace 清单）、Python 3.9+（仅一个探测脚本）。

**Spec：** `docs/specs/2026-11-18-workflow-design.md`

## 全局约束

- 工作流层**不得出现任何具体技术栈的命令**（`mvn` / `pnpm` / `npm` 等），命令只来自 `profile.commands.*`。
- 所有 Python 代码兼容 3.9+，且在 Windows 下可用（不依赖 `python3` 别名，用 `sys.executable`）。
- 不改动 Trellis 的 `task.py`、任何 hook 脚本、`inject-*.py`。
- 禁用清单外的 Superpowers 技能，不得在文档中推荐使用。
- 路径一律用正斜杠书写，避免跨平台问题。
- 提交信息用中文，遵循 `<type>: <描述>`。

## Review Focus

以下是最容易在实现中被忽略、而一旦出错会让整套机制失效的点，每个都要有任务覆盖：

1. **状态 tag 缺失** → 面包屑退化，流程强制力归零。验证方式：脚本逐个检查 6 个 tag 成对出现。
2. **状态名与 `task.json` 实际写入值不一致** → 面包屑永远命中不了自定义块。验证方式：用真实 `set-meta` 写入后跑 hook。
3. **profile 键名与 skill 读取处不一致** → 命令永远为空。验证方式：skill 里引用 `profile.commands.<key>` 的键集合与探测脚本产出的键集合做集合比对。
4. **探测脚本在无匹配构建文件时崩溃** → 新项目初始化失败。验证方式：空目录用例。
5. **`gh:user/repo/path` 路径解析不符预期** → 安装命令失效。验证方式：本地 fixture 实测（见 Task 8）。

---

## 文件结构

| 文件 | 职责 |
| --- | --- |
| `.claude-plugin/plugin.json` | Claude Code plugin 清单 |
| `.claude-plugin/marketplace.json` | 兼作 plugin marketplace 索引 |
| `trellis/index.json` | Trellis marketplace 索引（仅 `type: workflow` 条目） |
| `trellis/workflows/rigor.md` | 流程权威，唯一 |
| `trellis/specs/generic/*/index.md` | 栈无关规范骨架 |
| `trellis/specs/guides/index.md` | 跨包思考指南 |
| `trellis/specs/stacks/{spring-boot,vue,node}/index.md` | 可选栈规范骨架 |
| `skills/wf-review/SKILL.md` | 复核执行细则 |
| `skills/wf-dispatch/SKILL.md` | 派发决策细则 |
| `skills/wf-preflight/SKILL.md` | 挂机前检查细则 |
| `skills/wf-init/SKILL.md` | 初始化：跑 `trellis init` + 探测画像 |
| `agents/wf-reviewer-adversarial.md` | 对抗型复核者 |
| `agents/wf-reviewer-consistency.md` | 一致性复核者 |
| `templates/prd.md` / `design.md` | 规划产物模板 |
| `templates/dispatch-plan.md` / `review-report.md` | 派发与复核产物模板 |
| `scripts/detect_profile.py` | 项目画像探测 |
| `tests/test_detect_profile.py` | 探测脚本测试 |
| `README.md` | 安装、升级、禁用清单 |

---

### Task 1: 仓库骨架与清单

**Files:**
- Create: `.gitignore`、`README.md`、`.claude-plugin/plugin.json`、`.claude-plugin/marketplace.json`

**Interfaces:**
- Produces: plugin 名 `ai-workflow`；后续任务依赖此名称。

- [ ] **Step 1: 初始化仓库**

```bash
cd /d/project/ai-workflow
git init
```

- [ ] **Step 2: 写 `.gitignore`**

内容：`.DS_Store`、`__pycache__/`、`*.pyc`、`.venv/`、`node_modules/`。

- [ ] **Step 3: 写 `.claude-plugin/plugin.json`**

只写最小合法字段，skills / agents / commands 走目录约定自动发现：

```json
{
  "name": "ai-workflow",
  "version": "0.1.0",
  "description": "通用 AI 开发工作流：Trellis 流程权威 + 独立复核 + 并行派发",
  "author": { "name": "caoguangqian" },
  "license": "MIT",
  "keywords": ["workflow", "trellis", "review", "dispatch"]
}
```

- [ ] **Step 4: 写 `.claude-plugin/marketplace.json`**

```json
{
  "name": "ai-workflow",
  "owner": { "name": "caoguangqian" },
  "plugins": [
    {
      "name": "ai-workflow",
      "source": "./",
      "description": "通用 AI 开发工作流：Trellis 流程权威 + 独立复核 + 并行派发"
    }
  ]
}
```

- [ ] **Step 5: 验证 JSON 合法**

Run: `node -e "JSON.parse(require('fs').readFileSync('.claude-plugin/plugin.json','utf8')); JSON.parse(require('fs').readFileSync('.claude-plugin/marketplace.json','utf8')); console.log('ok')"`
Expected: `ok`

- [ ] **Step 6: 提交**

```bash
git add .gitignore .claude-plugin
git commit -m "chore: 初始化 ai-workflow 仓库与插件清单"
```

---

### Task 2: 流程权威 `trellis/workflows/rigor.md`

**Files:**
- Create: `trellis/workflows/rigor.md`

**Interfaces:**
- Consumes: 无
- Produces: 6 个状态 tag（`no_task`、`task_error`、`planning`、`reviewing`、`dispatching`、`in_progress`）；后续 skill 与脚本按这些名字引用状态。

- [ ] **Step 1: 写文件头与核心原则**

必含五条：先规划后实现；规范注入而非记忆；一切落盘；一次一个任务；完成后回写 spec。注明本 workflow 为非 native，`trellis update` 不覆盖。

- [ ] **Step 2: 写 Phase Index 与 6 个 tag 块**

每个 tag 块格式：

```
[workflow-state:<status>]
<Task 信息行由 hook 自动生成，此处只写正文>
- 当前阶段允许：<列举>
- 明确禁止：<列举>
- 退出条件：<硬性条件>
- 下一步命令：<可直接复制执行>
[/workflow-state:<status>]
```

正文要求：

| 状态 | 允许 | 禁止 | 退出条件 |
| --- | --- | --- | --- |
| `no_task` | 新建任务、分流判定 | 改业务代码 | 任务已创建 |
| `planning` | 写 `prd.md` / `design.md`、登记 context | 改业务代码、`task.py start` | 产物齐备且清单非空 |
| `reviewing` | 派发两个复核者、修订产物 | 改业务代码、跳过复核 | 某轮 0 个 P0/P1 |
| `dispatching` | 写 `dispatch.md`、等用户批准 | 派发 agent、改业务代码 | 用户明确批准 |
| `in_progress` | 按组执行、每组检查提交 | 跨组并行、跳过检查点 | 全部组完成 |
| `task_error` | 修复 `task.json` | 一切其他操作 | 记录可读 |

- [ ] **Step 3: 写 Phase 1（Plan）步骤 1.0–1.5**

1.0 建任务（`task.py create`）→ 1.1 需求探索（一次一问，先查代码再问人）→ 1.2 调研（可选）→ 1.3 登记上下文（`add-context`）→ 1.4 复核（调 `wf-review`，写 `reviewing` 状态）→ 1.5 派发设计（调 `wf-dispatch`，写 `dispatching` 状态）。

每步必须写明：执行的命令、产物路径、失败时的回退。

- [ ] **Step 4: 写任务分流规则**

轻量档条件（单文件、无契约变更、`spec/` 无对应条目）→ `planning` 直接 `in_progress`；标准档走全流程；拿不准按标准档。轻量档须在 `prd.md` 顶部写 `tier: light` 与理由。

- [ ] **Step 5: 写 Phase 2（Execute）与 Phase 3（Finish）**

Phase 2：并行组内并发派发；组内 agent 禁止 git；每组后立即 check + commit；检查点失败则停止并回退。
Phase 3：复盘 → spec 更新 → 提交 → 归档。

- [ ] **Step 6: 写 Superpowers 边界表**

允许：TDD、systematic-debugging、verification-before-completion、requesting/receiving-code-review。
禁用：brainstorming、writing-plans、executing-plans、subagent-driven-development、using-git-worktrees、dispatching-parallel-agents。每项一行禁用理由。

- [ ] **Step 7: 验证 tag 成对且字符集合法**

Run:
```bash
python -c "import re,sys; s=open('trellis/workflows/rigor.md',encoding='utf-8').read(); o=re.findall(r'\[workflow-state:([A-Za-z0-9_-]+)\]',s); c=re.findall(r'\[/workflow-state:([A-Za-z0-9_-]+)\]',s); print(sorted(o)); print(sorted(c)); sys.exit(0 if sorted(o)==sorted(c) and len(o)==6 else 1)"
```
Expected: 两组各 6 项且完全相同，退出码 0

- [ ] **Step 8: 提交**

```bash
git add trellis/workflows/rigor.md
git commit -m "feat: 添加自定义流程权威 rigor workflow"
```

---

### Task 3: Trellis 索引与 spec 骨架

**Files:**
- Create: `trellis/index.json`
- Create: `trellis/specs/guides/index.md`
- Create: `trellis/specs/generic/{error-handling,logging,configuration,testing-strategy,commit-convention}/index.md`
- Create: `trellis/specs/stacks/{spring-boot,vue,node}/index.md`

**Interfaces:**
- Consumes: Task 2 的 `workflows/rigor.md`
- Produces: `-r` 下载后 `.trellis/spec/` 的目录布局，供 `get_context.py --mode packages` 发现。

- [ ] **Step 1: 写 `trellis/index.json`**

```json
{
  "templates": [
    {
      "id": "rigor",
      "type": "workflow",
      "name": "Rigor Workflow",
      "description": "规划复核派发三阶段硬闸门",
      "path": "workflows/rigor.md"
    }
  ]
}
```

- [ ] **Step 2: 写 5 个 generic spec 的 `index.md`**

每份 20–40 行，含「开发前检查清单」与「质量检查」两节，正文给出可执行契约条目（禁止只写原则）。内容栈无关，不得出现具体命令。

- [ ] **Step 3: 写 `guides/index.md`**

跨包思考指南：何时需要看另一个包；契约变更的传播路径；如何判断一次改动是局部还是跨层。

- [ ] **Step 4: 写 3 个 stack spec 骨架**

每份 15–25 行，只写该栈特有的可执行契约（如 spring-boot：分层职责、异常处理边界、事务边界）。命令仍留空，由 profile 提供。

- [ ] **Step 5: 验证索引与文件一致**

Run:
```bash
python -c "import json,os,sys; d=json.load(open('trellis/index.json',encoding='utf-8')); missing=[t['path'] for t in d['templates'] if not os.path.exists(os.path.join('trellis',t['path']))]; print('missing:',missing); sys.exit(1 if missing else 0)"
```
Expected: `missing: []`，退出码 0

- [ ] **Step 6: 提交**

```bash
git add trellis/index.json trellis/specs
git commit -m "feat: 添加 Trellis 市场索引与 spec 骨架"
```

---

### Task 4: 两个复核者

**Files:**
- Create: `agents/wf-reviewer-adversarial.md`
- Create: `agents/wf-reviewer-consistency.md`

**Interfaces:**
- Consumes: `templates/review-report.md` 的格式（Task 6 实现；本任务先按 §5.3 的格式写死）
- Produces: 报告条目字段 `ID / 定位 / 分类 / 严重度 / 置信度 / 问题 / 依据 / 建议`

- [ ] **Step 1: 写对抗型复核者**

frontmatter：`name: wf-reviewer-adversarial`，`description` 写明触发场景（规划产物收敛后、进入派发前）。正文必含：
- 只找：反例、边界、不可实现的描述、遗漏的前置条件
- 不找：措辞、内部一致性、新需求
- **输入契约**：由调用方提供文件路径清单；额外读取的文件必须列出并说明理由
- **禁止输入**：作者的推理过程、上一轮报告、会话摘要
- 输出格式：逐条按 §5.3 字段
- 判定尺度：P0 = 会导致返工/数据错误/架构作废

- [ ] **Step 2: 写一致性复核者**

同样结构，但：
- 只找：PRD ↔ design 矛盾、与代码/接口契约冲突、语义漂移、术语不一致
- 不找：新需求、实现细节偏好
- 强制动作：把 PRD 中每个断言与引用到的代码/契约原文逐条对照

- [ ] **Step 3: 验证 frontmatter 与字段完整**

Run:
```bash
python -c "import re,sys,pathlib; ok=True
for p in ['agents/wf-reviewer-adversarial.md','agents/wf-reviewer-consistency.md']:
    s=pathlib.Path(p).read_text(encoding='utf-8')
    fm=re.match(r'---\n(.*?)\n---',s,re.S)
    need=['name:','description:']
    miss=[n for n in need if not fm or n not in fm.group(1)]
    print(p,'missing:',miss); ok=ok and not miss
sys.exit(0 if ok else 1)"
```
Expected: 两项均 `missing: []`

- [ ] **Step 4: 提交**

```bash
git add agents
git commit -m "feat: 添加对抗型与一致性复核者"
```

---

### Task 5: 三个执行技能

**Files:**
- Create: `skills/wf-review/SKILL.md`
- Create: `skills/wf-dispatch/SKILL.md`
- Create: `skills/wf-preflight/SKILL.md`

**Interfaces:**
- Consumes: Task 2 的状态名；Task 4 的复核者名；`profile.concurrency.max_parallel`
- Produces: 各 skill 的 `name` 与 `description`，供 `rigor.md` 引用

- [ ] **Step 1: 写 `wf-review`**

frontmatter `name: wf-review`，`description` 含触发词「复核 / review / 收敛」。正文：
- 前置检查：`prd.md` 存在；复杂任务需 `design.md`
- 输入清单生成规则（显式列路径；含 spec 条目与契约文件）
- 并行派发两个复核者（互不可见对方报告）
- 汇总规则：`reviewer-proposed` 进 backlog；P0 二选一
- 判停与轮次上限 5；写 `review/rounds.md`

- [ ] **Step 2: 写 `wf-dispatch`**

frontmatter `name: wf-dispatch`。正文：
- 三层冲突判定（文件 / 契约 / 运行时），每层给判定命令（如 `git diff --name-only`）
- 读 `profile.shared_resources` 与 `profile.forbidden_parallel`
- 生成 `dispatch.md`，等待用户批准
- 执行铁律：组内禁 git；每组后立即 check + commit

- [ ] **Step 3: 写 `wf-preflight`**

frontmatter `name: wf-preflight`。正文：
- 挂机前单向审：只问「哪一处最可能导致全盘返工」，强制排序取前 1
- 检查点划分：按并行组，逐组 commit
- 产出 `preflight.md`，含中止条件

- [ ] **Step 4: 验证 frontmatter 与交叉引用**

Run:
```bash
python -c "import re,sys,pathlib; names=[]; ok=True
for p in pathlib.Path('skills').glob('*/SKILL.md'):
    s=p.read_text(encoding='utf-8'); m=re.search(r'^name:\s*(\S+)',s,re.M)
    names.append(m.group(1) if m else None); ok=ok and bool(m)
print('skills:',sorted(n for n in names if n)); sys.exit(0 if ok and len(names)==3 else 1)"
```
Expected: 打印 3 个 skill 名，退出码 0

- [ ] **Step 5: 提交**

```bash
git add skills
git commit -m "feat: 添加复核、派发与挂机前检查技能"
```

---

### Task 6: 四个产物模板

**Files:**
- Create: `templates/prd.md`、`templates/design.md`、`templates/dispatch-plan.md`、`templates/review-report.md`

**Interfaces:**
- Consumes: 无
- Produces: `review-report.md` 的字段集合必须与 Task 4 的复核者输出一致

- [ ] **Step 1: 写 `prd.md` 模板**

必含：`tier: light|standard`、目标、非目标、验收标准（可测）、未决问题、涉及契约。验收标准每条必须能对应一个检查命令或一个人工判定动作。

- [ ] **Step 2: 写 `design.md` 模板**

必含：架构决策与理由、被否决的替代方案及否决理由、跨层影响、回滚方式。

- [ ] **Step 3: 写 `dispatch-plan.md` 模板**

严格按设计文档 §6.3 的四节：变更面、冲突矩阵、并行组、检查点与 git 策略。

- [ ] **Step 4: 写 `review-report.md` 模板**

字段与 §5.3 完全一致；附严重度定义表与分类说明。

- [ ] **Step 5: 验证字段一致**

Run:
```bash
python -c "import sys,pathlib; t=pathlib.Path('templates/review-report.md').read_text(encoding='utf-8'); need=['ID','定位','分类','严重度','置信度','问题','依据','建议']; miss=[n for n in need if n not in t]; print('missing:',miss); sys.exit(1 if miss else 0)"
```
Expected: `missing: []`

- [ ] **Step 6: 提交**

```bash
git add templates
git commit -m "feat: 添加 PRD、设计、派发与复核模板"
```

---

### Task 7: 项目画像探测脚本

**Files:**
- Create: `scripts/__init__.py`、`scripts/detect_profile.py`
- Test: `tests/test_detect_profile.py`

**Interfaces:**
- Consumes: 无
- Produces: `detect(root: Path) -> dict`，键为 `commands.{lint,typecheck,test,build}`、`shared_resources: list[str]`、`forbidden_parallel: list[str]`；CLI `--root <path> [--dry-run] [--write]`

- [ ] **Step 1: 写失败测试**

```python
from pathlib import Path
from scripts.detect_profile import detect

def test_java_maven(tmp_path: Path):
    (tmp_path / "pom.xml").write_text("<project/>", encoding="utf-8")
    p = detect(tmp_path)
    assert p["commands"]["test"] == "./mvnw test"
    assert p["commands"]["build"] == "./mvnw -DskipTests package"

def test_node_pnpm(tmp_path: Path):
    (tmp_path / "package.json").write_text(
        '{"scripts":{"lint":"eslint .","test":"vitest","build":"vite build"}}',
        encoding="utf-8",
    )
    p = detect(tmp_path)
    assert p["commands"]["lint"] == "pnpm lint"
    assert p["commands"]["build"] == "pnpm build"
    assert p["commands"]["typecheck"] == ""

def test_shared_resources_detected(tmp_path: Path):
    (tmp_path / "docker-compose.prod.yml").write_text("", encoding="utf-8")
    assert "docker-compose.prod.yml" in detect(tmp_path)["shared_resources"]

def test_empty_project_no_crash(tmp_path: Path):
    p = detect(tmp_path)
    assert p["commands"]["test"] == ""
    assert p["shared_resources"] == []
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/test_detect_profile.py -v`
Expected: FAIL（`ModuleNotFoundError: scripts.detect_profile`）

- [ ] **Step 3: 实现 `detect`**

规则：
- `pom.xml` 存在 → `build: ./mvnw -DskipTests package`、`test: ./mvnw test`，`lint`/`typecheck` 留空。
- `package.json` 的 `scripts` 有对应键 → 用 `pnpm <script>`（`pnpm-lock.yaml` 存在时），否则 `npm run <script>`。
- 仅当 `scripts` 含该键才填；缺键留空。
- `docker-compose*.yml`、`.env.prod`、`.env` → 进 `shared_resources`。
- `src/main/resources/db/migration/` 或 `migrations/` 存在 → 进 `forbidden_parallel`。
- 目录不存在或读不了 → 对应字段留空，绝不抛异常。

- [ ] **Step 4: 跑测试确认通过**

Run: `python -m pytest tests/test_detect_profile.py -v`
Expected: 4 passed

- [ ] **Step 5: 实现 CLI**

`--dry-run` 打印 YAML；`--write` 在 `.trellis/config.yaml` 末尾追加或替换 `profile:` 段。写之前备份为 `config.yaml.bak`。

- [ ] **Step 6: 对真实项目试跑（只读）**

Run: `python scripts/detect_profile.py --root /d/project/ganheng-evaluating --dry-run`
Expected: 输出含 `test: ./mvnw test`、`shared_resources` 含 `docker-compose.prod.yml`、`max_parallel: 3`；不写任何文件

- [ ] **Step 7: 提交**

```bash
git add scripts tests
git commit -m "feat: 添加项目画像探测脚本"
```

---

### Task 8: 初始化技能与端到端验证

**Files:**
- Create: `skills/wf-init/SKILL.md`

**Interfaces:**
- Consumes: Task 7 的 `detect_profile.py --write`
- Produces: 新项目可复现的初始化序列

- [ ] **Step 1: 写 `wf-init`**

正文步骤：确认目标项目 → 执行 `trellis init --claude --workflow rigor --workflow-source <src> --registry <src> -u <name>` → 跑 `detect_profile.py --write` → 提示补空命令 → 校验 `.trellis/workflow.md` 是自定义版（含 `[workflow-state:reviewing]`）→ 输出下一步命令。

- [ ] **Step 2: 建临时项目做端到端验证**

```bash
mkdir -p /d/project/_scratch/wf-e2e && cd /d/project/_scratch/wf-e2e && git init
```

把 `trellis/workflows/rigor.md` 手工放到 `.trellis/workflow.md`，并复制 plugin 与 spec 骨架（本步先用本地复制，远程 `gh:` 源在 Step 4 单独实测）。

- [ ] **Step 3: 验证状态切换与面包屑**

```bash
python .trellis/scripts/task.py create "验证任务"
python .trellis/scripts/task.py set-meta <task-dir> status reviewing
python .trellis/scripts/task.py current
```
手工触发 `inject-workflow-state.py`，把 `task.json` 内容从 stdin 传入。
Expected: 输出 `<workflow-state>` 块，`Status` 行为 `reviewing`，正文含「派发两个复核者」

- [ ] **Step 4: 记录 §12 四条假设的实测结果**

逐条实测并写入 `README.md` 的「已知限制」节：
1. `gh:user/repo/path` 在 `--workflow-source` 与 `--registry` 下的解析
2. plugin marketplace 与 trellis registry 共存
3. Windows 下 `{{PYTHON_CMD}}` 探测结果
4. `set-meta status` 后面包屑识别

- [ ] **Step 5: 提交**

```bash
git add skills/wf-init README.md
git commit -m "feat: 添加初始化技能并记录实测结论"
```

---

### Task 9: README 与收尾

**Files:**
- Modify: `README.md`

- [ ] **Step 1: 写 README**

必含：定位、安装两条命令、升级方式、状态机图、禁用技能清单、已知限制（来自 Task 8）、目录说明。

- [ ] **Step 2: 全量结构校验**

Run:
```bash
python -c "import json,pathlib,sys,re
ok=True
for f in ['trellis/index.json','.claude-plugin/plugin.json','.claude-plugin/marketplace.json']:
    json.loads(pathlib.Path(f).read_text(encoding='utf-8'))
w=pathlib.Path('trellis/workflows/rigor.md').read_text(encoding='utf-8')
o=re.findall(r'\[workflow-state:([A-Za-z0-9_-]+)\]',w)
print('tags:',sorted(o)); ok = ok and len(o)==6
sys.exit(0 if ok else 1)"
```
Expected: 3 个 JSON 均可解析，tags 6 个，退出码 0

- [ ] **Step 3: 提交**

```bash
git add -A
git commit -m "docs: 完善 README 与安装说明"
```

---

## 执行说明

- 任务 1–7 相互独立，可按顺序做，也可并行（文件不交集）。
- 任务 8 依赖 1–7 全部完成。
- 任务 9 依赖 8。
- 每个任务的最后一步是提交；如果中途某个验证失败，**不要跳到下一个任务**。

## 计划自审

- **spec 覆盖**：设计文档 §3–§10 均有对应任务。§7 项目画像落在 Task 7；§10 安装与升级落在 Task 8/9。§12 实测假设落在 Task 8 Step 4。
- **缺口修正**：设计文档 §7 说「初始化时自动探测」，但没定义机制——本计划补了 `scripts/detect_profile.py` 与 `wf-init`，属于让设计可实现的必需件，不是新增功能。
- **类型一致**：`profile.commands` 的四个键在 Task 7 与 Task 5 中同名；状态名在 Task 2、5、8 中一致。
- **比例**：计划长度约为设计文档的 2 倍，主要是可执行的验证命令，可接受。

## 执行结果修正（2026-11-18 实测）

Task 8 的端到端验证发现三处计划与现实不符，已就地修正：

1. **`task.py set-meta status <v>` 不写顶层 `status`**，而是写进 `meta.status`。面包屑读的是顶层字段，因此按原计划的自定义状态机**完全不生效，且不报错**。
   修正：新增 `scripts/wf_status.py` 直接写顶层字段，并在写入前校验 workflow.md 中存在对应 `[workflow-state:*]` 块（挡住 tag 缺失导致的静默退化）。`rigor.md`、`wf-review`、`wf-dispatch` 中的全部命令已替换。
2. **`task.py create` 要求 `--description`，中文标题无法自动生成 slug**。
   修正：建任务命令统一改为 `create "<标题>" --slug <slug> --description "<交付>"`。
3. **Monorepo 下顶层命令应留空**。原 `detect_profile.py` 只探测根目录，对 `backend/` + `fronted/` 这类结构探测不到任何命令。
   修正：探测根目录与一级子目录；恰好一个构建单元时自动填顶层命令，多个时留空并把各包命令打印到 stderr 供人工填写（符合设计「探测不到就留空，不猜」）。

Task 7 的测试从 4 个扩到 9 个（覆盖 maven 有无 wrapper、gradle、pnpm/npm、空目录、坏 package.json），另加 `tests/test_wf_status.py` 5 个，共 14 个，全部通过。
