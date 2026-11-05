"""M5 live check against the published GitHub Pages site (not localhost).

    python notebooks/live_check.py [URL]

Desktop 1400x900 and phone 390x844: console errors, geology/terrain/labels loaded,
tour runs through all stops, About links, favicon and og:image URLs, gzipped size of
geology.geojson. Writes notebooks/m5_*.png.
"""

import sys
from pathlib import Path

import requests
from playwright.sync_api import sync_playwright

URL = sys.argv[1] if len(sys.argv) > 1 else "https://kevinalexandr19.github.io/arabian-geology-3d/"
OUT = Path(__file__).resolve().parent
CHROMIUM = "/opt/pw-browsers/chromium" if Path("/opt/pw-browsers/chromium").is_file() else None
ARGS = ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"]
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) arabia3d-live-check"}
errors = {"desktop": [], "phone": []}

STATE_JS = """() => ({
  geology: map.isSourceLoaded('geology') && map.querySourceFeatures('geology').length,
  terrain: !!map.getTerrain(),
  dem_m_at_center: Math.round(map.queryTerrainElevation(map.getCenter()) ?? NaN),
  cities_rendered: map.queryRenderedFeatures({layers: ['city-label-a', 'city-label-b', 'city-label-c']
                     .filter((l) => map.getLayer(l))}).length,
  roads_rendered: map.queryRenderedFeatures({layers: ['roads-motorway', 'roads-trunk']}).length,
  loading_hidden: getComputedStyle(document.getElementById('loading')).display === 'none'
                  || document.getElementById('loading').hidden,
})"""


def watch(page, key):
    page.on("console", lambda m: m.type == "error" and errors[key].append(m.text))
    page.on("pageerror", lambda e: errors[key].append(str(e)))
    # ERR_ABORTED = MapLibre cancelling tiles it no longer needs while the camera moves; not an error.
    page.on("requestfailed", lambda r: "ERR_ABORTED" not in (r.failure or "")
            and errors[key].append(f"request failed: {r.url} {r.failure}"))


def idle(page):
    page.wait_for_function("map.isSourceLoaded('geology') && map.areTilesLoaded() && !map.isMoving()",
                           timeout=240_000, polling=500)
    page.wait_for_timeout(1500)


def caption(page):
    return page.inner_text("#caption h3") if page.is_visible("#caption") else None


def run_tour(page, prefix, n_shots):
    """Start the tour from the intro button and follow it to the end; screenshot the first n_shots stops."""
    page.click("#intro-tour")
    seen = []
    for _ in range(600):  # up to ~10 min under software GL
        cap = caption(page)
        if cap and (not seen or seen[-1] != cap):
            seen.append(cap)
            if len(seen) <= n_shots:
                page.wait_for_function("!map.isMoving()", timeout=60_000, polling=250)
                page.wait_for_timeout(800)
                cap = caption(page) or cap  # name the file after the stop actually on screen
                page.screenshot(path=OUT / f"{prefix}_stop{cap.split('.')[0]}.png")
        if page.evaluate("document.getElementById('tour-stop').disabled") and len(seen) > 1:
            break
        page.wait_for_timeout(1000)
    return [c.split(".")[0] for c in seen]


with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=CHROMIUM, args=ARGS)

    # ---- Desktop ----
    page = browser.new_page(viewport={"width": 1400, "height": 900})
    watch(page, "desktop")
    page.goto(URL)
    page.wait_for_function("typeof map !== 'undefined' && map.loaded()", timeout=180_000)
    idle(page)
    print("desktop state:", page.evaluate(STATE_JS))
    page.mouse.move(800, 450)
    page.wait_for_timeout(1500)
    print("desktop readout:", page.inner_text("#readout").replace("\n", " | "))
    page.screenshot(path=OUT / "m5_desktop.png")

    # About links + favicon/og:image from the live DOM.
    page.click('[data-open="about-win"]')
    links = page.eval_on_selector_all("#about-win a", "as => as.map((a) => [a.textContent.trim(), a.href])")
    meta = page.evaluate("""() => ({
      og_image: document.querySelector('meta[property="og:image"]').content,
      og_url: document.querySelector('meta[property="og:url"]').content,
      icons: [...document.querySelectorAll('link[rel~="icon"], link[rel="apple-touch-icon"]')].map((l) => l.href),
      last_updated: document.querySelector('.made time').textContent,
    })""")
    page.locator("#about-win .win").screenshot(path=OUT / "m5_desktop_about.png")
    page.click("#about-win .win-close")

    seen = run_tour(page, "m5_desktop", 3)
    print("desktop tour, stops seen while polling:", seen,
          "| finished:", page.evaluate("document.getElementById('tour-stop').disabled"))
    # Software GL makes screenshots slower than a tour stop, so shoot every stop via its bookmark too.
    page.evaluate("document.querySelector('details.tour').open = true")
    for i in range(page.locator("#bookmarks button").count()):
        page.locator("#bookmarks button").nth(i).click()
        page.wait_for_timeout(500)
        idle(page)
        page.screenshot(path=OUT / f"m5_desktop_stop{i + 1}.png")
    page.click("#cap-home") if page.is_visible("#cap-home") else page.click("#tour-home")
    page.close()

    # ---- Phone ----
    phone = browser.new_page(viewport={"width": 390, "height": 844}, device_scale_factor=2,
                             is_mobile=True, has_touch=True)
    watch(phone, "phone")
    phone.goto(URL)
    phone.wait_for_function("typeof map !== 'undefined' && map.loaded()", timeout=180_000)
    idle(phone)
    print("phone state:", phone.evaluate(STATE_JS))
    phone.screenshot(path=OUT / "m5_phone.png")
    phone.click("#panel-open")
    phone.wait_for_timeout(600)
    phone.screenshot(path=OUT / "m5_phone_panel.png")
    phone.click('[data-open="about-win"]')
    phone.wait_for_timeout(300)
    phone.screenshot(path=OUT / "m5_phone_about.png")
    phone.click("#about-win .win-close")  # opening a window already hid the panel
    phone.wait_for_timeout(400)
    seen_p = run_tour(phone, "m5_phone", 0)
    print("phone tour, stops seen:", seen_p,
          "| finished:", phone.evaluate("document.getElementById('tour-stop').disabled"))
    for i in (1, 4, 6):  # Asir, Tuwaiq, Hajar via bookmarks, waiting for tiles
        phone.click("#panel-open")
        phone.evaluate("document.querySelector('details.tour').open = true")
        phone.locator("#bookmarks button").nth(i).click()
        phone.wait_for_timeout(500)
        idle(phone)
        phone.screenshot(path=OUT / f"m5_phone_stop{i + 1}.png")
    phone.close()
    browser.close()

# ---- HTTP checks ----
print("\nmeta:", {k: v for k, v in meta.items() if k != "icons"})
for url in [*meta["icons"], meta["og_image"], meta["og_url"]]:
    r = requests.get(url, headers=UA, timeout=60)
    print(f"  {r.status_code}  {r.headers.get('content-type', ''):<24} {url}")
print("About links:")
for text, href in links:
    try:
        r = requests.get(href, headers=UA, timeout=60, allow_redirects=True)
        code = r.status_code
    except requests.RequestException as e:
        code = f"error {e.__class__.__name__}"
    print(f"  {code}  {text:<28} {href}")
r = requests.get(URL + "data/geology.geojson", headers={**UA, "Accept-Encoding": "gzip"}, stream=True, timeout=120)
wire = int(r.headers.get("content-length", 0))
body = len(r.content)
print(f"\ngeology.geojson: {r.headers.get('content-encoding')} transfer {wire / 1e6:.2f} MB, "
      f"uncompressed {body / 1e6:.2f} MB")
for k, v in errors.items():
    print(f"console errors ({k}):", v or "none")
