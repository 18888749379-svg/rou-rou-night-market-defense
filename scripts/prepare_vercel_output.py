from __future__ import annotations

import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WEB_OUTPUT = ROOT / "build" / "webapp" / "build" / "web"
VERCEL_OUTPUT = ROOT / ".vercel" / "output"


def main() -> None:
    if not (WEB_OUTPUT / "index.html").is_file():
        raise RuntimeError("Run scripts/build_web.py before preparing the Vercel output")
    if ROOT.resolve() not in VERCEL_OUTPUT.resolve().parents:
        raise RuntimeError(f"Refusing to clear unexpected output path: {VERCEL_OUTPUT}")

    shutil.rmtree(VERCEL_OUTPUT, ignore_errors=True)
    shutil.copytree(WEB_OUTPUT, VERCEL_OUTPUT / "static")
    (VERCEL_OUTPUT / "config.json").write_text(
        json.dumps({"version": 3}, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Vercel prebuilt output written to: {VERCEL_OUTPUT}")


if __name__ == "__main__":
    main()
