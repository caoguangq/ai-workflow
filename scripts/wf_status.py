"""写入 Trellis 任务的状态。

`task.py set-meta status <v>` 只写 `meta.status`，而面包屑 hook 读的是顶层
`status`，因此自定义状态无法通过 set-meta 生效。本脚本直接写顶层字段，
并在写入前校验流程文件里存在对应的 state tag——tag 缺失时面包屑会静默退化，
这是最难排查的故障，必须在此处拦住。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from pathlib import Path

ALLOWED_STATUSES = ("bootstrapping", "planning", "reviewing", "dispatching", "in_progress")
TAG_RE = re.compile(r"\[workflow-state:([A-Za-z0-9_-]+)\]")


def find_repo_root(start: Path) -> Path:
    for candidate in [start, *start.parents]:
        if (candidate / ".trellis").is_dir():
            return candidate
    raise SystemExit("未找到 .trellis 目录，请在项目根目录执行")


def read_workflow_states(repo_root: Path) -> set[str]:
    workflow = repo_root / ".trellis" / "workflow.md"
    if not workflow.exists():
        raise SystemExit(f"未找到 {workflow}")
    return set(TAG_RE.findall(workflow.read_text(encoding="utf-8")))


def resolve_task_dir(repo_root: Path, value: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = (repo_root / path).resolve()
    if not (path / "task.json").exists():
        raise SystemExit(f"{path} 下没有 task.json")
    return path


def write_status(task_dir: Path, status: str) -> None:
    task_json = task_dir / "task.json"
    data = json.loads(task_json.read_text(encoding="utf-8"))
    data["status"] = status
    fd, tmp = tempfile.mkstemp(dir=str(task_dir), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.replace(tmp, task_json)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="写入 Trellis 任务状态（顶层 status 字段）")
    parser.add_argument("task_dir", help="任务目录，例如 .trellis/tasks/11-18-foo")
    parser.add_argument("status", choices=ALLOWED_STATUSES, help="目标状态")
    args = parser.parse_args(argv)

    repo_root = find_repo_root(Path.cwd())
    task_dir = resolve_task_dir(repo_root, args.task_dir)

    states = read_workflow_states(repo_root)
    if args.status not in states:
        raise SystemExit(
            f"workflow.md 中没有 [workflow-state:{args.status}] 块，"
            f"面包屑会静默退化。现有状态：{sorted(states)}"
        )

    write_status(task_dir, args.status)
    print(f"status -> {args.status}  ({task_dir.name})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
