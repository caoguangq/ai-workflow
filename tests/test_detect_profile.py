from pathlib import Path

from scripts.detect_profile import detect


def test_maven_with_wrapper(tmp_path: Path) -> None:
    (tmp_path / "pom.xml").write_text("<project/>", encoding="utf-8")
    (tmp_path / "mvnw").write_text("", encoding="utf-8")
    p = detect(tmp_path)
    assert p["commands"]["test"] == "./mvnw test"
    assert p["commands"]["build"] == "./mvnw -DskipTests package"


def test_maven_without_wrapper(tmp_path: Path) -> None:
    (tmp_path / "pom.xml").write_text("<project/>", encoding="utf-8")
    p = detect(tmp_path)
    assert p["commands"]["test"] == "mvn test"


def test_gradle(tmp_path: Path) -> None:
    (tmp_path / "build.gradle").write_text("", encoding="utf-8")
    p = detect(tmp_path)
    assert p["commands"]["build"] == "gradle build"
    assert p["commands"]["test"] == "gradle test"


def test_node_pnpm(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text(
        '{"scripts":{"lint":"eslint .","test":"vitest","build":"vite build"}}',
        encoding="utf-8",
    )
    (tmp_path / "pnpm-lock.yaml").write_text("", encoding="utf-8")
    p = detect(tmp_path)
    assert p["commands"]["lint"] == "pnpm lint"
    assert p["commands"]["test"] == "pnpm test"
    assert p["commands"]["build"] == "pnpm build"
    assert p["commands"]["typecheck"] == ""


def test_node_npm_when_no_pnpm_lock(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text('{"scripts":{"test":"jest"}}', encoding="utf-8")
    p = detect(tmp_path)
    assert p["commands"]["test"] == "npm run test"


def test_shared_resources_detected(tmp_path: Path) -> None:
    (tmp_path / "docker-compose.prod.yml").write_text("", encoding="utf-8")
    (tmp_path / ".env.prod").write_text("", encoding="utf-8")
    found = detect(tmp_path)["shared_resources"]
    assert "docker-compose.prod.yml" in found
    assert ".env.prod" in found


def test_forbidden_parallel_detected(tmp_path: Path) -> None:
    (tmp_path / "migrations").mkdir()
    assert "migrations/" in detect(tmp_path)["forbidden_parallel"]


def test_build_manifest_is_forbidden_parallel(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text('{"scripts":{}}', encoding="utf-8")
    assert "package.json" in detect(tmp_path)["forbidden_parallel"]


def test_nested_build_manifest_is_forbidden_parallel(tmp_path: Path) -> None:
    backend = tmp_path / "backend"
    backend.mkdir()
    (backend / "pom.xml").write_text("<project/>", encoding="utf-8")
    assert "backend/pom.xml" in detect(tmp_path)["forbidden_parallel"]


def test_empty_project_no_crash(tmp_path: Path) -> None:
    p = detect(tmp_path)
    assert p["commands"] == {"lint": "", "typecheck": "", "test": "", "build": ""}
    assert p["shared_resources"] == []
    assert p["concurrency"]["max_parallel"] == 3


def test_broken_package_json_no_crash(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text("{not json", encoding="utf-8")
    p = detect(tmp_path)
    assert p["commands"]["test"] == ""
