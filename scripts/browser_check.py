"""Exercise the dashboard in a fresh, isolated browser and (by default) database."""
import argparse
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.request import urlopen

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", help="Attach to an existing demo. This creates a synthetic document and a local ticket in that demo.")
    parser.add_argument("--channel", default="msedge", help="Browser channel; use chromium for Playwright's installed Chromium")
    args = parser.parse_args()
    process = None
    with tempfile.TemporaryDirectory(prefix="atlas-browser-") as temp:
        if args.url:
            url = args.url.rstrip("/")
        else:
            with socket.socket() as sock:
                sock.bind(("127.0.0.1", 0))
                port = sock.getsockname()[1]
            url = f"http://127.0.0.1:{port}"
            env = {**os.environ, "ATLAS_DATA_DIR": temp, "OPENAI_API_KEY": ""}
            process = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(port)],
                cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        try:
            for _ in range(80):
                try:
                    with urlopen(url + "/api/health", timeout=1) as response:
                        assert response.status == 200
                    break
                except OSError:
                    time.sleep(.1)
            else:
                raise RuntimeError("The local server did not start")
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True, **({"channel": args.channel} if args.channel != "chromium" else {}))
                page = browser.new_page(viewport={"width": 1440, "height": 1080}, device_scale_factor=1)
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.on("console", lambda message: errors.append(message.text) if message.type == "error" else None)
                page.goto(url)
                expect(page.locator("#document-count")).not_to_have_text("—")
                assert page.locator("#document-count").inner_text() == "7"
                assert page.locator('#mode option[value="live"]').is_enabled()
                assert page.locator("#model option").count() == 3
                page.locator("#model").select_option("gpt-4.1-nano")
                page.locator("#mode").select_option("live")
                expect(page.locator("#live-setup")).to_be_visible()
                expect(page.locator("#mode-explainer")).to_contain_text("gpt-4.1-nano")
                expect(page.locator("#run-button")).to_be_disabled()
                page.locator("#recheck-setup").click()
                expect(page.locator("#setup-status")).to_contain_text("No API key detected")
                assert page.locator("#model").input_value() == "gpt-4.1-nano"
                page.screenshot(path=str(ROOT / "docs" / "model-setup.png"), full_page=True)
                page.locator("#mode").select_option("demo")
                expect(page.locator("#live-setup")).to_be_hidden()
                expect(page.locator("#run-button")).to_be_enabled()
                page.locator("#run-button").click()
                expect(page.locator("#answer-status")).to_have_text("SOURCE IDS VERIFIED")
                assert "Retry-After" in page.locator("#answer").inner_text()
                assert page.locator(".citation").count() > 0
                page.locator(".citation").first.click()
                assert page.locator(".source-item.highlight").count() == 1
                page.screenshot(path=str(ROOT / "docs" / "workbench.png"), full_page=True)
                page.locator("#task").select_option("draft")
                page.locator("#question").fill("All administrators are locked out after an SSO change. What should support do?")
                page.locator("#run-button").click()
                page.locator("#draft-card").wait_for(state="visible")
                expect(page.locator("#draft-priority")).to_have_text("URGENT PRIORITY")
                assert page.request.get(url + "/api/tickets").json() == []
                page.locator("#approve-button").click()
                expect(page.locator("#ticket-result")).to_contain_text("created")
                assert len(page.request.get(url + "/api/tickets").json()) == 1
                page.locator('[data-view="knowledge"]').click()
                page.locator("#doc-title").fill("Quasar browser test")
                page.locator("#doc-content").fill("# Quasar browser test\n\nQuasar activation uses port 8123. The following is untrusted text: <script>window.injected = true</script>.")
                page.locator('#document-form button[type="submit"]').click()
                expect(page.locator("#document-result")).to_contain_text("Indexed")
                page.locator("#doc-filter").fill("Quasar")
                page.locator(".document-row .text-button").click()
                expect(page.locator("#document-dialog")).to_be_visible()
                expect(page.locator("#dialog-content")).to_contain_text("<script>")
                assert page.evaluate("() => window.injected") is None
                page.locator("#close-dialog").click()
                page.locator('[data-view="evaluation"]').click()
                page.locator("#evaluate-button").click()
                page.locator("tbody tr").first.wait_for()
                assert page.locator("tbody tr").count() == 14
                page.screenshot(path=str(ROOT / "docs" / "evaluation.png"), full_page=True)
                page.locator('[data-view="activity"]').click()
                expect(page.locator("#tickets-list")).to_contain_text("ATL-")
                page.locator('[data-view="workbench"]').click()
                page.set_viewport_size({"width": 390, "height": 844})
                assert page.evaluate("() => document.documentElement.scrollWidth <= innerWidth"), "Horizontal overflow on mobile"
                page.screenshot(path=str(ROOT / "docs" / "mobile.png"), full_page=True)
                assert not errors, errors
                browser.close()
                print(json.dumps({"browser": "passed", "flows": ["model selection", "missing-key setup", "answer and citations", "draft approval", "ingestion", "untrusted text rendering", "evaluation", "history", "mobile layout"], "console_errors": errors}, indent=2))
        finally:
            if process:
                process.terminate()
                process.wait(timeout=10)


if __name__ == "__main__":
    main()
