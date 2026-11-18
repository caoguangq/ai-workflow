"""探测项目画像（profile），供工作流读取。

只做事实探测，不做猜测：某个命令探测不到就留空，由人来补。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

COMMAND_KEYS = ("lint", "typecheck", "test", "build")
DEFAULT_MAX_PARALLEL = 3
SHARED_RESOURCE_PATTERNS = ("docker-compose*.yml", ".env", ".env.prod", ".env.*.example")
FORBIDDEN_DIRS = ("migrations", "src/main/resources/db/migration")


def _empty_commands() -> dict[str, str]:
    return {k: "" for k in COMMAND_KEYS}


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _node_commands(pkg_dir: Path, rel: str) -> dict[str, str]:
    data = _read_json(pkg_dir / "package.json")
    if data is None:
        return _empty_commands()
    scripts = data.get("scripts")
    if not isinstance(scripts, dict):
        return _empty_commands()

    use_pnpm = (pkg_dir / "pnpm-lock.yaml").exists()
    prefix = "" if rel in ("", ".") else (f"-C {rel} " if use_pnpm else f"--prefix {rel} ")

    commands = _empty_commands()
    for key in COMMAND_KEYS:
        if key in scripts:
            if use_pnpm:
                commands[key] = f"pnpm {prefix}{key}"
            else:
                commands[key] = f"npm {prefix}run {key}"
    return commands


def _java_commands(pkg_dir: Path, rel: str) -> dict[str, str] | None:
    commands = _empty_commands()
    has_maven = (pkg_dir / "pom.xml").exists()
    has_gradle = (pkg_dir / "build.gradle").exists() or (pkg_dir / "build.gradle.kts").exists()
    if not has_maven and not has_gradle:
        return None

    if has_maven:
        wrapper = (pkg_dir / "mvnw").exists()
        base = "./mvnw" if wrapper and rel in ("", ".") else "mvn"
        if rel not in ("", "."):
            base = f"{base} -f {rel}/pom.xml"
        commands["test"] = f"{base} test"
        commands["build"] = f"{base} -DskipTests package"
        return commands

    wrapper = (pkg_dir / "gradlew").exists()
    base = "./gradlew" if wrapper and rel in ("", ".") else "gradle"
    if rel not in ("", "."):
        base = f"{base} -p {rel}"
    commands["test"] = f"{base} test"
    commands["build"] = f"{base} build"
    return commands


def _detect_packages(root: Path) -> list[dict[str, Any]]:
    """根目录与一级子目录中的构建单元。"""
    packages: list[dict[str, Any]] = []

    java = _java_commands(root, ".")
    if java is not None:
        packages.append({"name": root.name, "path": ".", "commands": java})
    node = _node_commands(root, ".")
    if any(node.values()):
        packages.append({"name": root.name, "path": ".", "commands": node})

    try:
        children = sorted(p for p in root.iterdir() if p.is_dir())
    except OSError:
        return packages

    for child in children:
        if child.name.startswith(".") or child.name in ("node_modules", "target", "dist", "build"):
            continue
        java = _java_commands(child, child.name)
        if java is not None:
            packages.append({"name": child.name, "path": child.name, "commands": java})
            continue
        node = _node_commands(child, child.name)
        if any(node.values()):
            packages.append({"name": child.name, "path": child.name, "commands": node})
    return packages


def _shared_resources(root: Path) -> list[str]:
    found: list[str] = []
    for pattern in SHARED_RESOURCE_PATTERNS:
        for path in sorted(root.glob(pattern)):
            rel = path.relative_to(root).as_posix()
            if rel not in found:
                found.append(rel)
    return found


def _forbidden_parallel(root: Path) -> list[str]:
    found: list[str] = []
    candidates = list(FORBIDDEN_DIRS)
    try:
        for child in root.iterdir():
            if child.is_dir() and not child.name.startswith("."):
                for name in FORBIDDEN_DIRS:
                    candidates.append(f"{child.name}/{name}")
    except OSError:
        pass
    for name in candidates:
        if (root / name).is_dir():
            entry = name if name.endswith("/") else f"{name}/"
            if entry not in found:
                found.append(entry)
    return found


def detect(root: Path) -> dict[str, Any]:
    root = Path(root)
    packages = _detect_packages(root) if root.exists() else []

    # 只有一个构建单元时才自动填顶层命令；多个说明是 monorepo，留给人工指定。
    if len(packages) == 1:
        commands = dict(packages[0]["commands"])
    else:
        commands = _empty_commands()

    return {
        "commands": commands,
        "concurrency": {"max_parallel": DEFAULT_MAX_PARALLEL},
        "shared_resources": _shared_resources(root),
        "forbidden_parallel": _forbidden_parallel(root),
        "packages": packages,
    }


def to_yaml(profile: dict[str, Any]) -> str:
    lines = ["profile:", "  commands:"]
    for key in COMMAND_KEYS:
        lines.append(f'    {key}: "{profile["commands"][key]}"')
    lines.append("  concurrency:")
    lines.append(f'    max_parallel: {profile["concurrency"]["max_parallel"]}')
    for key in ("shared_resources", "forbidden_parallel"):
        values = profile[key]
        if values:
            lines.append(f"  {key}:")
            lines.extend(f"    - {v}" for v in values)
        else:
            lines.append(f"  {key}: []")
    return "\n".join(lines) + "\n"


def write_profile(root: Path, profile: dict[str, Any]) -> Path:
    config = root / ".trellis" / "config.yaml"
    if not config.exists():
        raise SystemExit(f"未找到 {config}，请先执行 trellis init")
    original = config.read_text(encoding="utf-8")
    (config.parent / "config.yaml.bak").write_text(original, encoding="utf-8")

    block = to_yaml(profile)
    if re.search(r"^profile:\s*$", original, re.M):
        new_text = re.sub(r"^profile:\n(?:[ \t].*\n|\s*\n)*", block, original, count=1, flags=re.M)
    else:
        new_text = original.rstrip("\n") + "\n\n" + block
    config.write_text(new_text, encoding="utf-8")
    return config


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="探测项目画像并写入 .trellis/config.yaml")
    parser.add_argument("--root", default=".", help="项目根目录")
    parser.add_argument("--dry-run", action="store_true", help="只打印，不写文件")
    parser.add_argument("--write", action="store_true", help="写入 .trellis/config.yaml")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    profile = detect(root)
    print(to_yaml(profile), end="")

    if len(profile["packages"]) > 1:
        print("\n# 检测到多个构建单元（顶层命令留空，需人工指定）：", file=sys.stderr)
        for pkg in profile["packages"]:
            print(f"#   {pkg['path']}", file=sys.stderr)
            for key, value in pkg["commands"].items():
                if value:
                    print(f"#     {key}: {value}", file=sys.stderr)
    missing = [k for k, v in profile["commands"].items() if not v]
    if missing:
        print(f"# 未探测到的命令（需人工补齐）：{', '.join(missing)}", file=sys.stderr)

    if args.write and not args.dry_run:
        path = write_profile(root, profile)
        print(f"# 已写入 {path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
