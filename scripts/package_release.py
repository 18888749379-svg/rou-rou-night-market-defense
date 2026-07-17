from __future__ import annotations

from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "dist" / "rou-rou-night-market-defense-clean.zip"
ROOT_FILES = ["README.md", "LICENSE", "requirements.txt", "run_game.bat"]
ROOT_DIRS = ["assets", "src"]


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.unlink(missing_ok=True)
    with ZipFile(OUTPUT, "w", ZIP_DEFLATED) as archive:
        for name in ROOT_FILES:
            path = ROOT / name
            if path.is_file():
                archive.write(path, path.name)
        for directory in ROOT_DIRS:
            base = ROOT / directory
            for path in base.rglob("*"):
                if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc":
                    archive.write(path, path.relative_to(ROOT))
    print(f"Clean release written to: {OUTPUT}")


if __name__ == "__main__":
    main()
