"""Record the README demo GIF (assets/demo.gif).

Drives the running app with Playwright through a short scripted flow — ask a
question, watch the answer stream in with a citation, expand a retrieved source,
then run a query in the retrieval inspector — records it to webm, extracts
scaled frames with ffmpeg, and assembles a palette-quantized GIF with Pillow.

Prerequisites:
    pip install playwright pillow
    playwright install chromium        # or set CHROME_PATH to a Chromium binary
    ffmpeg on PATH                     # or set FFMPEG (Playwright bundles one)
    # and the app running (see start.sh):
    ./start.sh                         # backend :8000 + frontend :5173

Run:
    python scripts/record_demo.py

Env overrides:
    APP_URL       app base URL          (default http://localhost:5173)
    CHROME_PATH   Chromium executable   (default: Playwright's managed browser)
    FFMPEG        ffmpeg executable     (default: "ffmpeg" on PATH)
    GIF_OUT       output GIF path       (default: <repo>/assets/demo.gif)
"""

import glob
import os
import subprocess
import tempfile
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

REPO = Path(__file__).resolve().parent.parent
URL = os.environ.get("APP_URL", "http://localhost:5173")
OUT = Path(os.environ.get("GIF_OUT", REPO / "assets" / "demo.gif"))
CHROME_PATH = os.environ.get("CHROME_PATH")      # None -> Playwright's Chromium
FFMPEG = os.environ.get("FFMPEG", "ffmpeg")

VW, VH = 1200, 760      # capture (viewport) size
GIF_W = 740             # output width; height scales proportionally
FPS = 10
COLORS = 128


def record(video_dir: str) -> str:
    launch_kwargs = {"headless": True}
    if CHROME_PATH:
        launch_kwargs["executable_path"] = CHROME_PATH
    with sync_playwright() as p:
        browser = p.chromium.launch(**launch_kwargs)
        ctx = browser.new_context(
            viewport={"width": VW, "height": VH},
            record_video_dir=video_dir,
            record_video_size={"width": VW, "height": VH},
        )
        page = ctx.new_page()
        page.goto(URL, wait_until="networkidle")
        page.wait_for_timeout(1000)                       # show the empty state

        # Ask a question with a substantive answer, watch it stream.
        page.click(".suggestions button >> nth=2")        # E2EE passphrase Q
        page.wait_for_selector(".msg.assistant .sources", timeout=30000)
        page.wait_for_function("() => !document.querySelector('.caret')", timeout=120000)
        page.wait_for_timeout(700)

        # Expand the top source passage (shows its cosine + BM25 scores).
        page.click(".msg.assistant .source .source-head >> nth=0")
        page.wait_for_selector(".source.open .source-body", timeout=5000)
        page.wait_for_timeout(1200)

        # Jump to the retrieval inspector and run a query.
        page.click("nav.tabs button >> nth=1")
        page.wait_for_timeout(500)
        box = page.get_by_placeholder("Type a query to inspect retrieval…")
        box.click()
        box.type("what is the API rate limit for a free token", delay=35)
        page.get_by_role("button", name="Retrieve").click()
        page.wait_for_selector(".results li", timeout=30000)
        page.wait_for_timeout(1100)

        ctx.close()                                       # flushes the video file
        browser.close()
    return glob.glob(os.path.join(video_dir, "*.webm"))[0]


def to_frames(webm: str, frames_dir: str) -> list:
    subprocess.run(
        [FFMPEG, "-y", "-i", webm, "-r", str(FPS),
         "-vf", f"scale={GIF_W}:-1", os.path.join(frames_dir, "f_%04d.png")],
        check=True, capture_output=True,
    )
    return sorted(glob.glob(os.path.join(frames_dir, "f_*.png")))


def build_gif(frame_paths: list) -> None:
    frames = [Image.open(p).convert("RGB") for p in frame_paths]
    # One shared adaptive palette (from a mid frame) -> smaller file, no flicker.
    pal = frames[len(frames) // 2].quantize(colors=COLORS, method=Image.MEDIANCUT)
    quant = [f.quantize(palette=pal, dither=Image.Dither.NONE) for f in frames]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    quant[0].save(
        OUT, save_all=True, append_images=quant[1:],
        duration=int(1000 / FPS), loop=0, optimize=True, disposal=2,
    )


def main() -> None:
    with tempfile.TemporaryDirectory() as vd, tempfile.TemporaryDirectory() as fd:
        webm = record(vd)
        frame_paths = to_frames(webm, fd)
        print(f"frames: {len(frame_paths)}")
        build_gif(frame_paths)
    print(f"saved {OUT}  ({OUT.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
