from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
STAGING = ROOT / "build" / "webapp"
OUTPUT = STAGING / "build" / "web"
PYGBAG_CDN = "https://pygame-web.github.io/archives/0.9/"
WEB_IMAGE_LIMITS = {
    "alley_background.png": (1280, 720),
    "ending_victory.png": (1280, 720),
    "ending_defeat.png": (1280, 720),
    "grill_resource.png": (320, 480),
}
DEFAULT_WEB_IMAGE_LIMIT = (256, 256)


def optimize_web_images() -> None:
    image_dir = STAGING / "assets" / "images"
    before_bytes = 0
    after_bytes = 0
    for path in image_dir.glob("*.png"):
        before_bytes += path.stat().st_size
        limit = WEB_IMAGE_LIMITS.get(path.name, DEFAULT_WEB_IMAGE_LIMIT)
        temporary = path.with_suffix(".web.png")
        with Image.open(path) as image:
            image.load()
            image.thumbnail(limit, Image.Resampling.LANCZOS, reducing_gap=3.0)
            image.save(temporary, format="PNG", optimize=True, compress_level=9)
        temporary.replace(path)
        after_bytes += path.stat().st_size
    print(
        "Web images optimized: "
        f"{before_bytes / 1024 / 1024:.1f} MB -> {after_bytes / 1024 / 1024:.1f} MB"
    )


def prepare_staging() -> None:
    resolved = STAGING.resolve()
    if ROOT.resolve() not in resolved.parents:
        raise RuntimeError(f"Refusing to clear unexpected staging path: {resolved}")
    shutil.rmtree(STAGING, ignore_errors=True)
    STAGING.mkdir(parents=True, exist_ok=True)
    shutil.copytree(ROOT / "assets", STAGING / "assets")
    optimize_web_images()
    for source in (ROOT / "src").glob("*.py"):
        if source.name == "main.py":
            continue
        shutil.copy2(source, STAGING / source.name)
    shutil.copy2(ROOT / "scripts" / "web_main.py", STAGING / "main.py")


def main() -> None:
    prepare_staging()
    result = subprocess.run(
        [sys.executable, "-m", "pygbag", "--build", "--cdn", PYGBAG_CDN, str(STAGING)],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        details = result.stderr.strip() or result.stdout.strip() or "No error output"
        raise RuntimeError(f"Pygbag build failed:\n{details}")
    index = OUTPUT / "index.html"
    if not index.is_file():
        raise RuntimeError(f"Pygbag did not create {index}")
    if PYGBAG_CDN not in index.read_text(encoding="utf-8"):
        raise RuntimeError(f"Pygbag output does not use the expected CDN: {PYGBAG_CDN}")
    print(f"Web build written to: {OUTPUT}")


if __name__ == "__main__":
    main()
