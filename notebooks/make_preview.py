"""Render docs/preview.png, the 1200x630 link-preview card (og:image), from the live viewer.

Flat (pitch 0) view of the whole peninsula, UI hidden, with a title and data credits.
Serve the site first:  python -m http.server -d docs 8000
Then:                  python notebooks/make_preview.py
"""

from pathlib import Path

from playwright.sync_api import sync_playwright

URL = "http://localhost:8000/"
OUT = Path(__file__).resolve().parents[1] / "docs" / "preview.png"
CHROMIUM = "/opt/pw-browsers/chromium" if Path("/opt/pw-browsers/chromium").is_file() else None

HIDE_UI = """
  .panel, .panel-open, .intro, .caption, .loading, .readout, .maplibregl-control-container { display: none !important; }
  #map { position: absolute !important; inset: 0; }
  .card-title {
    position: absolute; left: 44px; top: 46px; width: 330px; z-index: 10;
    font: 15px/1.45 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; color: #1d232a;
  }
  .card-title h1 { font-size: 46px; line-height: 1.05; margin: 0 0 10px; letter-spacing: -.01em; }
  .card-title p { margin: 0 0 14px; font-size: 19px; color: #3a4550; }
  .card-title ul { list-style: none; margin: 18px 0 0; padding: 0; font-size: 13px; }
  .card-title li { display: flex; align-items: center; gap: 8px; margin: 4px 0; }
  .card-title .sw { width: 18px; height: 11px; border-radius: 2px; border: 1px solid rgba(0,0,0,.25); }
  .card-credit {
    position: absolute; right: 14px; bottom: 10px; z-index: 10;
    font: 11px system-ui, sans-serif; color: #3a4550; background: rgba(255,255,255,.75);
    padding: 3px 8px; border-radius: 3px;
  }
"""

TITLE_JS = """(classes) => {
  const d = document.createElement('div');
  d.className = 'card-title';
  d.innerHTML = '<h1>Arabia 3D</h1><p>Geology × topography of the Arabian Peninsula</p>' +
    'Interactive 3D map with a guided tour' +
    '<ul>' + classes.map(c => `<li><span class="sw" style="background:${c.colour}"></span>${c.name}</li>`).join('') + '</ul>';
  document.body.appendChild(d);
  const c = document.createElement('div');
  c.className = 'card-credit';
  c.textContent = 'Geology: USGS OFR 97-470-B · Terrain: AWS Terrain Tiles (Mapzen) · Cities: Natural Earth';
  document.body.appendChild(c);
}"""

with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=CHROMIUM,
                                args=["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"])
    page = browser.new_page(viewport={"width": 1200, "height": 630})
    page.goto(URL)
    page.wait_for_function("typeof map !== 'undefined' && map.loaded()", timeout=120_000)
    page.add_style_tag(content=HIDE_UI)
    classes = page.evaluate("fetch('data/units.json').then(r => r.json()).then(j => j.classes)")
    page.evaluate(TITLE_JS, classes)
    # Peninsula to the right of the title block; flat view so it reads as a map.
    page.evaluate("""() => {
      map.resize();
      // Roads clutter the geology at this scale; the card shows geology, relief and cities only.
      ['roads-motorway', 'roads-trunk', 'roads-primary'].forEach((l) => map.setLayoutProperty(l, 'visibility', 'none'));
      map.jumpTo({ ...map.cameraForBounds([[34.4, 12.4], [60.0, 32.2]],
                   { padding: { left: 400, right: 20, top: 16, bottom: 44 } }), pitch: 0, bearing: 0 });
    }""")
    page.wait_for_function("map.isSourceLoaded('geology') && map.areTilesLoaded() && !map.isMoving()",
                           timeout=180_000, polling=500)
    page.wait_for_timeout(3000)
    page.screenshot(path=OUT)
    browser.close()
print("wrote", OUT)
