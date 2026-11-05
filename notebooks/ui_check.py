"""UI check: first view (intro + loading), collapsible panel, tap-to-show stats, cursor readout, phone.

Serve the site first:  python -m http.server -d docs 8000
Then:                  python notebooks/ui_check.py
Writes notebooks/ui_*.png and prints console errors.
"""

from pathlib import Path

from playwright.sync_api import sync_playwright

URL = "http://localhost:8000/"
OUT = Path(__file__).resolve().parent
CHROMIUM = "/opt/pw-browsers/chromium" if Path("/opt/pw-browsers/chromium").is_file() else None
ARGS = ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"]
errors = []


def watch(page):
    page.on("console", lambda m: m.type == "error" and errors.append(m.text))
    page.on("pageerror", lambda e: errors.append(str(e)))


def idle(page):
    page.wait_for_function("map.isSourceLoaded('geology') && map.areTilesLoaded() && !map.isMoving()",
                           timeout=180_000, polling=500)
    page.wait_for_timeout(1500)


with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=CHROMIUM, args=ARGS)

    # Desktop
    page = browser.new_page(viewport={"width": 1400, "height": 900})
    watch(page)
    page.goto(URL)
    page.wait_for_selector("#loading", state="visible")
    page.screenshot(path=OUT / "ui_loading.png")
    page.wait_for_function("typeof map !== 'undefined' && map.loaded()", timeout=120_000)
    idle(page)
    print("loading hidden after load:", page.is_hidden("#loading"))
    page.mouse.move(900, 450)
    page.wait_for_timeout(1500)
    print("readout (hover):", page.inner_text("#readout"))
    page.screenshot(path=OUT / "ui_first_view.png")

    # Elevation accuracy at Jabal Shams (~3,009 m) and Riyadh (~600 m), independent of exaggeration.
    page.evaluate("map.jumpTo({center: [57.277, 23.216], zoom: 10})")
    page.wait_for_timeout(500)
    print("elevationAt Jabal Shams:", round(page.evaluate("elevationAt(57.2629, 23.2370)")),
          "| Riyadh:", round(page.evaluate("elevationAt(46.7, 24.65)")))
    page.evaluate("map.jumpTo({center: [45, 23], zoom: 5, pitch: 45})")

    # Tap a legend bar -> numbers; the class must stay switched on.
    page.locator("#legend .ebar").first.click()
    print("stats shown:", page.is_visible("#legend .estats"),
          "| class still on:", page.locator("#legend input").first.is_checked())
    # Open the other sections, then screenshot the panel.
    page.evaluate("document.querySelectorAll('details.sec').forEach((d) => d.open = true)")
    page.wait_for_timeout(300)
    page.locator(".panel").screenshot(path=OUT / "ui_panel_open.png")
    page.locator("details.about").scroll_into_view_if_needed()
    page.locator("details.about").screenshot(path=OUT / "ui_about.png")
    # Intro button starts the tour and hides the intro.
    page.evaluate("document.querySelectorAll('details.sec').forEach((d, i) => d.open = i === 0)")
    page.click("#intro-tour")
    page.wait_for_timeout(500)
    print("intro hidden on tour:", page.is_hidden("#intro"),
          "| tour running:", page.evaluate("document.getElementById('tour-stop').disabled === false"))
    page.screenshot(path=OUT / "ui_tour_running.png")
    page.click("#cap-home")
    page.wait_for_timeout(500)
    print("intro back on Home:", page.is_visible("#intro"))
    page.close()

    # Phone
    phone = browser.new_page(viewport={"width": 390, "height": 844}, device_scale_factor=2,
                             is_mobile=True, has_touch=True)
    watch(phone)
    phone.goto(URL)
    phone.wait_for_function("typeof map !== 'undefined' && map.loaded()", timeout=120_000)
    idle(phone)
    phone.screenshot(path=OUT / "ui_phone_first_view.png")
    phone.tap("#map", position={"x": 200, "y": 560})
    phone.wait_for_timeout(1500)
    print("phone readout (tap):", phone.inner_text("#readout"))
    phone.evaluate("document.querySelectorAll('.maplibregl-popup').forEach((p) => p.remove())")
    phone.click("#panel-open")
    phone.wait_for_timeout(600)
    phone.locator("#legend .ebar").nth(6).tap()
    phone.wait_for_timeout(300)
    phone.screenshot(path=OUT / "ui_phone_panel.png")
    phone.evaluate("document.querySelector('details.about').open = true")
    phone.locator("details.about").scroll_into_view_if_needed()
    phone.wait_for_timeout(300)
    phone.screenshot(path=OUT / "ui_phone_about.png")
    phone.close()
    browser.close()

print("console errors:", errors or "none")
