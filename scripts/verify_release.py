from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RELEASE = ROOT.parent / "肉肉守摊大战僵尸_Gitee发布版"

FORBIDDEN_DIRS = {
    ".git",
    ".venv",
    ".vercel",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "__pycache__",
    "build",
    "dist",
    "outputs",
    "venv",
}
FORBIDDEN_FILES = {
    "save_data.json",
    "save_data.json.bak",
    "save_data.json.tmp",
}
REQUIRED_PATHS = {
    "README.md",
    "LICENSE",
    "requirements.txt",
    "src/main.py",
    "src/game.py",
    "src/settings.py",
    "assets/images",
    "assets/audio",
}


def verify_release(release_dir: Path) -> list[str]:
    problems: list[str] = []
    if not release_dir.is_dir():
        return [f"发布目录不存在：{release_dir}"]

    for relative in sorted(REQUIRED_PATHS):
        if not (release_dir / relative).exists():
            problems.append(f"缺少必要内容：{relative}")

    for path in release_dir.rglob("*"):
        relative = path.relative_to(release_dir)
        if any(part in FORBIDDEN_DIRS for part in relative.parts):
            problems.append(f"包含禁止目录：{relative}")
            continue
        if path.name in FORBIDDEN_FILES:
            problems.append(f"包含本地存档：{relative}")
        elif path.is_file() and path.suffix.lower() in {".pyc", ".pyo", ".log"}:
            problems.append(f"包含缓存或日志：{relative}")

    return sorted(set(problems))


def main() -> int:
    release_dir = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else DEFAULT_RELEASE
    problems = verify_release(release_dir)
    if problems:
        print("发布目录检查失败：")
        for problem in problems:
            print(f"- {problem}")
        return 1
    print(f"发布目录检查通过：{release_dir}")
    print("未发现本地存档、Git 元数据、虚拟环境、构建缓存或日志。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
