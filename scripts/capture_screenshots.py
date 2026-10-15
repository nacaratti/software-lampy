"""Regenerates the README screenshots in docs/images/.

Drives a locally installed Edge or Chrome in headless mode over the Chrome
DevTools Protocol (using `websockets`, already a backend dependency — no
Playwright/Selenium download needed). For each page it navigates, clicks the
page's run button, waits for the result to render, and saves a PNG.

Usage (with backend + frontend dev servers running):

    python scripts/capture_screenshots.py                         # http://localhost:5173
    python scripts/capture_screenshots.py --url http://localhost:5174
    python scripts/capture_screenshots.py --only system modes      # subset
"""
from __future__ import annotations

import argparse
import asyncio
import base64
import itertools
import json
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

import websockets

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "docs" / "images"
WIDTH, HEIGHT = 1440, 900

BROWSER_CANDIDATES = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    "google-chrome",
    "chromium",
    "microsoft-edge",
]

# A small Yb MOPA for the System Builder shot: seed + 976 nm pump -> WDM ->
# double-clad Yb fiber -> OSA / power meter / beam profiler.
_EDGE_STYLE = {"animated": True, "markerEnd": {"type": "arrowclosed", "color": "hsl(var(--primary))"}}


def _n(nid, kind, label, x, y, **params):
    return {"id": nid, "type": kind, "position": {"x": x, "y": y},
            "data": {"label": label, "nodeKind": kind, "params": params}}


def _e(eid, src, dst, target_handle=None):
    e = {"id": eid, "source": src, "target": dst, **_EDGE_STYLE}
    if target_handle:
        e["targetHandle"] = target_handle
    return e


DEMO_SYSTEM = {
    "nodes": [
        _n("seed", "seed", "Seed 1064 nm", 0, 20, wavelength_nm=1064.0, power_w=0.5, linewidth_nm=0.1),
        _n("pump", "pump_source", "Pump 976 nm", 0, 200, wavelength_nm=976.0, power_w=40.0, linewidth_nm=0.5),
        _n("wdm", "coupler_wdm", "Pump combiner", 260, 60, insertion_loss_port1_db=0.3, insertion_loss_port2_db=0.4),
        _n("yb", "fiber_active", "Yb DC 20/400", 520, 50, ion="yb", core_radius_um=10.0,
           clad_radius_um=200.0, inner_cladding_radius_um=200.0, n_core=1.4515, n_clad=1.45,
           N_total=8e25, tau_ms=0.84, background_loss_db_m=0.005, length_m=5.0),
        _n("osa", "osa", "Spectrum analyzer", 790, -90, rbw_nm=0.1),
        _n("pm", "power_meter", "Power meter", 790, 50),
        _n("bp", "beam_profiler", "Beam profiler", 790, 170, grid_n=128, num_z=21, z_span_factor=6.0),
    ],
    "edges": [
        _e("e1", "seed", "wdm"),
        _e("e2", "pump", "wdm", "pump"),
        _e("e3", "wdm", "yb"),
        _e("e4", "yb", "osa"),
        _e("e5", "yb", "pm"),
        _e("e6", "yb", "bp"),
    ],
}

# JS helpers injected into every page.
_HELPERS = r"""
window.__lampy = {
  clickButton(text) {
    const b = [...document.querySelectorAll('button')].find(
      (el) => el.textContent.trim().startsWith(text) && !el.disabled);
    if (!b) return false;
    b.click();
    return true;
  },
  scrollMainTo(selector) {
    const main = document.querySelector('main');
    const el = selector ? document.querySelector(selector) : null;
    if (!main) return false;
    main.scrollTop = el ? el.getBoundingClientRect().top - main.getBoundingClientRect().top + main.scrollTop - 16 : 0;
    return true;
  },
  scrollMainToText(text) {
    // Smallest element whose text contains `text`, scrolled to the top of the viewport.
    const main = document.querySelector('main');
    const hits = [...main.querySelectorAll('*')].filter((e) => e.textContent.includes(text));
    const el = hits.find((e) => ![...e.children].some((c) => c.textContent.includes(text)));
    if (!el) return false;
    el.scrollIntoView({ block: 'start' });
    window.scrollBy(0, -76);  // clear the sticky top bar
    return true;
  },
  clickText(text) {
    const el = [...document.querySelectorAll('main *')].find(
      (e) => e.childElementCount === 0 && e.textContent.trim() === text);
    if (!el) return false;
    (el.closest('button,a,[role=button],li,[data-device-id]') || el).click();
    return true;
  },
  hasText(text) { return document.querySelector('main').innerText.includes(text); },
  hideToasts() {
    const st = document.createElement('style');
    st.textContent = '[data-sonner-toaster]{display:none!important}';
    document.head.appendChild(st);
    return true;
  },
  plots() { return document.querySelectorAll('.js-plotly-plot').length; },
};
"""


@dataclass
class Shot:
    name: str
    path: str
    run_button: str | None = None
    # JS expression that is truthy once the result is on screen
    ready: str = "true"
    after: list[str] = field(default_factory=list)  # JS run after `ready`
    settle_s: float = 1.5
    timeout_s: float = 180.0


SHOTS = [
    Shot("home", "/", settle_s=1.0),
    # Close the results drawer so the hero shows the blocks with their live result badges.
    Shot("system", "/system", run_button="Simulate",
         ready="document.body.innerText.includes('Nonlinear effects')",
         after=["document.querySelector('[aria-label=\"Close simulation results\"]')?.click()"], settle_s=2.5),
    Shot("modes", "/modes", run_button="Solve modes", ready="/modes? found/.test(document.body.innerText)",
         after=["__lampy.scrollMainToText('found')"]),
    Shot("power", "/power", run_button="Run ASE", ready="__lampy.hasText('Power evolution along fiber')",
         after=["__lampy.scrollMainToText('Power evolution along fiber')"], settle_s=2.0),
    Shot("power-ramp", "/power-ramp", run_button="Run sweep", ready="__lampy.hasText('SRS / SBS')",
         after=["__lampy.scrollMainToText('SRS / SBS')"], settle_s=2.0),
    Shot("gnlse", "/gnlse", run_button="Propagate", ready="__lampy.hasText('Spectral power evolution')",
         after=["__lampy.scrollMainToText('Temporal power evolution')"], settle_s=2.0),
    Shot("fbg", "/fbg", run_button="Run Simulation", ready="__lampy.plots() >= 1"),
    Shot("thermal", "/thermal", run_button="Run Simulation", ready="__lampy.plots() >= 2"),
    Shot("devices", "/devices", ready="__lampy.hasText('Coractive')",
         after=["__lampy.clickText('DCF-YB-20/128E')"], settle_s=1.5),
]


class Cdp:
    def __init__(self, ws):
        self.ws = ws
        self.ids = itertools.count(1)

    async def send(self, method: str, **params):
        msg_id = next(self.ids)
        await self.ws.send(json.dumps({"id": msg_id, "method": method, "params": params}))
        while True:
            msg = json.loads(await self.ws.recv())
            if msg.get("id") == msg_id:
                if "error" in msg:
                    raise RuntimeError(f"{method}: {msg['error']}")
                return msg.get("result", {})

    async def eval(self, expr: str):
        res = await self.send("Runtime.evaluate", expression=expr, returnByValue=True, awaitPromise=True)
        if "exceptionDetails" in res:
            raise RuntimeError(f"JS error in {expr!r}: {res['exceptionDetails'].get('text')}")
        return res.get("result", {}).get("value")

    async def wait_for(self, expr: str, timeout_s: float, what: str):
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            try:
                if await self.eval(expr):
                    return
            except RuntimeError:
                pass
            await asyncio.sleep(0.5)
        raise TimeoutError(f"timed out waiting for {what}: {expr}")

    async def goto(self, url: str):
        await self.send("Page.navigate", url=url)
        await self.wait_for("document.readyState === 'complete' && !!document.querySelector('main')", 60, "page load")
        await self.eval(_HELPERS)


def find_browser() -> str:
    for cand in BROWSER_CANDIDATES:
        path = cand if Path(cand).exists() else shutil.which(cand)
        if path:
            return str(path)
    sys.exit("No Edge/Chrome found — install one or add its path to BROWSER_CANDIDATES.")


async def capture(base_url: str, only: set[str] | None, port: int) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    profile = tempfile.mkdtemp(prefix="lampy-shots-")
    proc = subprocess.Popen([
        find_browser(), "--headless=new", f"--remote-debugging-port={port}",
        f"--user-data-dir={profile}", f"--window-size={WIDTH},{HEIGHT}",
        "--hide-scrollbars", "--force-color-profile=srgb", "--no-first-run", "about:blank",
    ])
    try:
        targets = None
        for _ in range(60):
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/list") as r:
                    targets = [t for t in json.load(r) if t.get("type") == "page"]
                if targets:
                    break
            except OSError:
                pass
            await asyncio.sleep(0.5)
        if not targets:
            sys.exit("Browser did not expose a DevTools page target.")

        async with websockets.connect(targets[0]["webSocketDebuggerUrl"], max_size=64 * 2**20) as ws:
            cdp = Cdp(ws)
            await cdp.send("Page.enable")
            await cdp.send("Runtime.enable")
            await cdp.send("Emulation.setDeviceMetricsOverride", width=WIDTH, height=HEIGHT,
                           deviceScaleFactor=1, mobile=False)
            await cdp.send("Emulation.setEmulatedMedia", features=[{"name": "prefers-color-scheme", "value": "dark"}])

            # Seed per-origin state: dark theme + the demo system on the canvas.
            await cdp.goto(base_url + "/")
            await cdp.eval(
                "localStorage.setItem('lampy.theme','dark');"
                f"localStorage.setItem('lampy-system-v1', {json.dumps(json.dumps(DEMO_SYSTEM))});"
            )

            for shot in SHOTS:
                if only and shot.name not in only:
                    continue
                print(f"[{shot.name}] {shot.path}", flush=True)
                await cdp.goto(base_url + shot.path)
                await asyncio.sleep(1.0)
                if shot.run_button:
                    await cdp.wait_for(f"__lampy.clickButton({json.dumps(shot.run_button)})", 30,
                                       f"run button '{shot.run_button}'")
                await cdp.wait_for(shot.ready, shot.timeout_s, f"{shot.name} result")
                await cdp.eval("__lampy.hideToasts()")
                for js in shot.after:
                    await cdp.eval(js)
                await asyncio.sleep(shot.settle_s)
                png = await cdp.send("Page.captureScreenshot", format="png")
                out = OUT_DIR / f"{shot.name}.png"
                out.write_bytes(base64.b64decode(png["data"]))
                print(f"  -> {out.relative_to(ROOT)}", flush=True)
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
        shutil.rmtree(profile, ignore_errors=True)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url", default="http://localhost:5173", help="frontend base URL")
    ap.add_argument("--only", nargs="*", help="subset of shot names: " + ", ".join(s.name for s in SHOTS))
    ap.add_argument("--port", type=int, default=9333, help="DevTools port for the headless browser")
    args = ap.parse_args()
    asyncio.run(capture(args.url.rstrip("/"), set(args.only) if args.only else None, args.port))


if __name__ == "__main__":
    main()
