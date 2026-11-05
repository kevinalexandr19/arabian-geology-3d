"""M4 check: load the viewer, click each bookmark, screenshot after the flight and tiles finish.

Serve the site first:  python -m http.server -d docs 8000
Then:                  python notebooks/m4_screenshots.py [stop numbers...]
"""

import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

CHROMIUM = "/opt/pw-browsers/chromium" if Path("/opt/pw-browsers/chromium").is_file() else None  # preinstalled in the cloud env
URL = "http://localhost:8000/"
OUT = Path(__file__).resolve().parent
# Resolve when the map is idle (flight over, tiles loaded), or after 90 s at most.
WAIT_IDLE = """() => new Promise((res) => {
  const t0 = performance.now();
  const check = () => {
    if ((map.areTilesLoaded() && !map.isMoving()) || performance.now() - t0 > 90000) res(performance.now() - t0);
    else setTimeout(check, 250);
  };
  check();
})"""

stops = [int(a) for a in sys.argv[1:]] or list(range(1, 9))
errors = []

with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=CHROMIUM, args=["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"])

    page = browser.new_page(viewport={"width": 1400, "height": 900})
    page.on("console", lambda m: m.type == "error" and errors.append(m.text))
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(URL)
    page.wait_for_function("typeof map !== 'undefined' && map.loaded()", timeout=120_000)
    page.evaluate(WAIT_IDLE)
    page.wait_for_timeout(1500)
    if 1 in stops:
        page.locator(".legend").screenshot(path=OUT / "m4_legend.png")
    for i in stops:
        page.locator("#bookmarks button").nth(i - 1).click()
        page.wait_for_timeout(500)
        page.evaluate(WAIT_IDLE)
        page.wait_for_timeout(1500)
        page.evaluate(WAIT_IDLE)
        page.wait_for_timeout(2500)  # let symbol labels fade in
        page.screenshot(path=OUT / f"m4_stop{i}.png")
        print("stop", i, flush=True); print( page.evaluate("[map.getCenter().toArray().map(v => +v.toFixed(2)), +map.getZoom().toFixed(2)]"))

    # Tour wiring: play, then a user drag must stop it.
    page.click("#tour-home")
    page.evaluate(WAIT_IDLE)
    page.click("#tour-play")
    page.wait_for_timeout(1000)
    playing = page.evaluate("document.getElementById('tour-stop').disabled === false")
    page.mouse.move(900, 450)
    page.mouse.down()
    page.mouse.move(1000, 500, steps=5)
    page.mouse.up()
    stopped = page.evaluate("document.getElementById('tour-stop').disabled === true")
    print(f"tour playing after start: {playing}; stopped by drag: {stopped}")
    page.close()

    phone = browser.new_page(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True)
    phone.on("console", lambda m: m.type == "error" and errors.append(m.text))
    phone.on("pageerror", lambda e: errors.append(str(e)))
    phone.goto(URL)
    phone.wait_for_function("typeof map !== 'undefined' && map.loaded()", timeout=120_000)
    phone.evaluate(WAIT_IDLE)
    phone.click("#panel-open")
    phone.wait_for_timeout(800)
    phone.screenshot(path=OUT / "m4_phone.png")
    phone.locator("#bookmarks button").nth(4).click()  # Hajar; closes the panel on phones
    phone.wait_for_timeout(500)
    phone.evaluate(WAIT_IDLE)
    phone.wait_for_timeout(2500)
    phone.screenshot(path=OUT / "m4_phone_stop5.png")
    phone.close()
    browser.close()

print("console errors:", errors or "none")
