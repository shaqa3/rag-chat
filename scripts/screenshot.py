"""Capture the README screenshot (assets/screenshot.png).

Drives the running app with Playwright: loads the chat, asks the first suggested
question, waits for the streamed cited answer to finish, expands the top source
passage, and screenshots at 2x for a crisp image.

Prerequisites:
    pip install playwright
    playwright install chromium        # or set CHROME_PATH to a Chromium binary
    # then, in two other shells:
    make backend                       # :8000  (or `make backend-offline`)
    make frontend                      # :5173

Run:
    python scripts/screenshot.py

Env overrides:
    APP_URL       app base URL          (default http://localhost:5173)
    CHROME_PATH   Chromium executable   (default: Playwright's managed browser)
    SHOT_OUT      output PNG path       (default: <repo>/assets/screenshot.png)
"""

import os
from pathlib import Path

from playwright.sync_api import sync_playwright

REPO = Path(__file__).resolve().parent.parent
URL = os.environ.get("APP_URL", "http://localhost:5173")
OUT = Path(os.environ.get("SHOT_OUT", REPO / "assets" / "screenshot.png"))
CHROME_PATH = os.environ.get("CHROME_PATH")  # None -> Playwright's own Chromium


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    launch_kwargs = {"headless": True}
    if CHROME_PATH:
        launch_kwargs["executable_path"] = CHROME_PATH

    with sync_playwright() as p:
        browser = p.chromium.launch(**launch_kwargs)
        page = browser.new_page(viewport={"width": 1280, "height": 900},
                                device_scale_factor=2)
        page.goto(URL, wait_until="networkidle")

        # Ask the first suggested question.
        page.click(".suggestions button >> nth=0")

        # Wait for sources to render and streaming to finish (caret gone).
        # Real llama3.2 generation is slower than the offline fallback.
        page.wait_for_selector(".msg.assistant .sources", timeout=30000)
        page.wait_for_function("() => !document.querySelector('.caret')", timeout=120000)

        # Expand the top source to show its passage + retrieval scores.
        page.click(".msg.assistant .source .source-head >> nth=0")
        page.wait_for_selector(".source.open .source-body", timeout=5000)
        page.wait_for_timeout(400)

        page.screenshot(path=str(OUT))
        print(f"saved {OUT}")
        browser.close()


if __name__ == "__main__":
    main()
