import json
from pathlib import Path

import pytest

from scripts.wf_status import ALLOWED_STATUSES, read_workflow_states, write_status


def _make_task(tmp_path: Path, status: str = "planning") -> Path:
    task_dir = tmp_path / "tasks" / "11-18-demo"
    task_dir.mkdir(parents=True)
    (task_dir / "task.json").write_text(
        json.dumps({"id": "demo", "status": status, "meta": {}}, ensure_ascii=False),
        encoding="utf-8",
    )
    return task_dir


def test_write_status_sets_top_level_field(tmp_path: Path) -> None:
    task_dir = _make_task(tmp_path)
    write_status(task_dir, "reviewing")
    data = json.loads((task_dir / "task.json").read_text(encoding="utf-8"))
    assert data["status"] == "reviewing"
    assert data["meta"] == {}


def test_write_status_keeps_other_fields(tmp_path: Path) -> None:
    task_dir = _make_task(tmp_path)
    write_status(task_dir, "dispatching")
    data = json.loads((task_dir / "task.json").read_text(encoding="utf-8"))
    assert data["id"] == "demo"


def test_read_workflow_states(tmp_path: Path) -> None:
    trellis = tmp_path / ".trellis"
    trellis.mkdir()
    (trellis / "workflow.md").write_text(
        "[workflow-state:planning]\nx\n[/workflow-state:planning]\n"
        "[workflow-state:reviewing]\ny\n[/workflow-state:reviewing]\n",
        encoding="utf-8",
    )
    assert read_workflow_states(tmp_path) == {"planning", "reviewing"}


def test_allowed_statuses_cover_workflow_states(tmp_path: Path) -> None:
    trellis = tmp_path / ".trellis"
    trellis.mkdir()
    workflow = Path(__file__).resolve().parents[1] / "trellis" / "workflows" / "rigor.md"
    (trellis / "workflow.md").write_text(workflow.read_text(encoding="utf-8"), encoding="utf-8")
    states = read_workflow_states(tmp_path)
    missing = {"planning", "reviewing", "dispatching", "in_progress"} - states
    assert not missing
    assert set(ALLOWED_STATUSES) <= states


def test_write_status_rejects_unknown(tmp_path: Path) -> None:
    task_dir = _make_task(tmp_path)
    with pytest.raises(SystemExit):
        # argparse choices 之外的取值由 CLI 层拦截；此处验证函数本身不做校验
        from scripts import wf_status

        wf_status.main([str(task_dir), "bogus"])
