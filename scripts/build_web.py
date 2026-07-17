from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STAGING = ROOT / "build" / "webapp"
OUTPUT = STAGING / "build" / "web"


def prepare_staging() -> None:
    resolved = STAGING.resolve()
    if ROOT.resolve() not in resolved.parents:
        raise RuntimeError(f"Refusing to clear unexpected staging path: {resolved}")
    shutil.rmtree(STAGING, ignore_errors=True)
    STAGING.mkdir(parents=True, exist_ok=True)
    shutil.copytree(ROOT / "assets", STAGING / "assets")
    for source in (ROOT / "src").glob("*.py"):
        if source.name == "main.py":
            continue
        shutil.copy2(source, STAGING / source.name)
    shutil.copy2(ROOT / "scripts" / "web_main.py", STAGING / "main.py")


def main() -> None:
    prepare_staging()
    subprocess.run(
        [sys.executable, "-m", "pygbag", "--build", str(STAGING)],
        cwd=ROOT,
        check=True,
    )
    index = OUTPUT / "index.html"
    if not index.is_file():
        raise RuntimeError(f"Pygbag did not create {index}")
    print(f"Web build written to: {OUTPUT}")


if __name__ == "__main__":
    main()
