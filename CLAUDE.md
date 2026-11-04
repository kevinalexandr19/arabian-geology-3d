# Arabia 3D — Geology × Topography of the Arabian Peninsula

## Goal
A static, interactive 3D web map of the Arabian Peninsula, hosted on GitHub Pages, that anyone can open from a link. Regional-scale geology is coloured and draped over 3D terrain, with city and road overlays. The point of the map is to let a viewer **see how geology correlates with topography**: the Arabian Shield vs. the cover sequence, escarpments, volcanic fields, sand seas and the Oman mountains.

Owner: geoscientist (petrology/geochemistry, Python). Communicate in English. Keep explanations short and technical.

## Hard requirements
- **Static only.** No backend, no build server at runtime, no API keys or tokens. It must work from GitHub Pages.
- **3D terrain** with a vertical-exaggeration control.
- **Geology** coloured by simplified regional class and draped on the terrain, with adjustable opacity.
- **Overlays:** major cities (labels) and major roads.
- **No country borders or admin boundaries anywhere.** That includes not using any third-party basemap that draws them. The coastline is fine.
- **Legend in a side panel.** Each class can be toggled on and off. Clicking a polygon shows a popup with the unit name, age, lithology and source.
- **Regional scale.** Generalise the geology to about 10–15 classes. Fine detail is not wanted; contrasts that line up with relief are.
- Works on desktop and is usable on a phone.

## Stack (defaults — change only with a stated reason)
- **Viewer:** MapLibre GL JS (from cdnjs/unpkg), plain HTML/CSS/JS, no framework, no bundler.
- **Terrain:** AWS Open Data "Terrain Tiles" in Terrarium encoding (`https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png`). They are public and need no key. Use them as a `raster-dem` source for both `terrain` and a `hillshade` layer. Include the attribution the dataset requires.
- **Geology:** USGS Open-File Report 97-470B, "Bedrock geology of the Arabian Peninsula and selected adjacent areas" (geo2bg), DOI 10.3133/ofr97470B. This is public domain, derived from the USGS–Aramco 1963 1:2,000,000 map. Find the data release (USGS ScienceBase or pubs.usgs.gov) and download the shapefile.
- **Cities and roads:** Natural Earth 1:10m `populated_places` and `roads` (public domain). Do NOT use the admin layers.
- **Label glyphs:** a public glyph endpoint, for example `https://demotiles.maplibre.org/font/{fontstack}/{range}.pbf`. If that is unreliable, self-host the glyph PBFs in the repo.
- **Processing:** Python 3.11+, with geopandas, shapely, pyproj, rasterio, numpy, requests. Put the scripts in `scripts/`, numbered in run order. Add an optional exploratory notebook in `notebooks/`, since the owner works in JupyterLab.

## Repository layout
```
scripts/        01_download.py, 02_geology.py, 03_overlays.py, 04_elevation_stats.py
data/raw/       downloaded sources (gitignored if > 50 MB total)
docs/           the published site (GitHub Pages serves /docs from main)
  index.html  app.js  style.css  data/*.geojson
notebooks/      optional exploration
README.md       what it is, the live link, how to rebuild, sources and licences
```

## Geology generalisation (two-level scheme)
geo2bg has a single age attribute, `GLG` (28 codes in the bbox). Each code is mapped to two levels in one editable CSV, `scripts/geology_classes.csv`, with columns `source_unit, source_description, level1_class, level1_colour, level2_class, level2_colour, notes`. Any assignment that is ambiguous is flagged `AMBIGUOUS:` in `notes` for owner review. `H2O` and `U` are `EXCLUDE` and are dropped.

**Level 1, "Generalized".** This follows the legend of a published generalized geologic map of the Arabian Peninsula:

| # | Class | Colour |
|---|---|---|
| 1 | Precambrian basement (Arabian Shield) | #E8456B |
| 2 | Paleozoic | #9DBF95 |
| 3 | Triassic | #8B3A9A |
| 4 | Jurassic | #2BA6C9 |
| 5 | Cretaceous | #6DBE45 |
| 6 | Paleocene and Eocene | #EE8E4A |
| 7 | Oligocene | #F8C88A |
| 8 | Miocene and Pliocene | #F2E35C |
| 9 | Volcanic rocks, Tertiary and Quaternary (harrats, Yemen traps) | #C79A00 (darkened from the reference #D9B400; ΔE vs class 8 was only ~15 under hillshade) |
| 10 | Eolian sand and gravel, mainly Quaternary | #F5EFAA |
| 11 | Ophiolite (Semail Nappe) and Hawasina allochthon | #3B5BA9 |

Known data limits (M1 inspection):
- **Classes 6 and 7 have no source units.** geo2bg `T` (Tertiary, about 708k km²) is undivided. Until the owner decides, it goes to a provisional L1 class "Tertiary sedimentary, undivided (PROVISIONAL)" (#F2A65A). Options are to map it all to class 6, to split it spatially from another source in M2, or to keep the provisional class.
- **Class 11 has no source units.** geo2bg does not separate the Semail ophiolite or the Hawasina allochthon. They are very likely inside `K` in Oman/UAE (about 44k km²).
- Class 8 holds only `QT` (Oman interior gravel fans), which is flagged as a possible class 10.

**Level 2, "Detailed".** These are the meaningful geo2bg subdivisions nested inside each L1 class, coloured as lighter or darker shades of the parent. There are 19 units, which is the most geo2bg supports; anything under about 1–2k km² is merged. Examples: Cambrian–Ordovician / Ordovician–Devonian / Carboniferous–Permian / Paleozoic undivided; Cretaceous vs. Upper Cretaceous–Paleogene; Yemen-trap Tertiary volcanics vs. harrats vs. Quaternary volcanics vs. Cenozoic intrusives; eolian sand vs. alluvium and gravel vs. Quaternary undivided vs. sabkha.

Simplify the geometry so that `docs/data/geology.geojson` is **under 8 MB**. Dissolve by L2 class (which also carries L1), then apply topology-preserving simplification. Every feature carries `l1`, `l1_colour`, `l2` and `l2_colour`.

**Viewer implications (M3/M4):**
- The legend has a **"Generalized / Detailed" toggle**. It switches the fill colour between `l1_colour` and `l2_colour`, and the legend between L1 entries and L2 entries nested under their L1 parent. Toggling class visibility works at both levels: hiding an L1 parent hides its children.
- **Popups show both levels** (L1 class and L2 unit), plus the source `GLG` code(s), age, lithology note and source citation.
- **Elevation stats are computed for both levels**. `elev_stats.json` has `level1` and `level2` blocks, and the legend shows the bars for the active level.

## "Geology × topography" features
- **Bookmarks / tour:** 6–8 camera presets with flyTo, pitch and bearing, each with a two-sentence caption. Suggested stops: the Hijaz–Asir escarpment and the Shield; Harrat Rahat / Harrat Khaybar; the Tuwaiq escarpment; the Rub' al Khali; the Hajar Mountains and the Semail ophiolite; the Yemen highlands and traps; Dhofar.
- **Elevation stats per class:** precompute the min, median and max elevation per geology class, at both Level 1 and Level 2, from Terrarium tiles sampled at a low zoom (z6–7). Show them in the legend as small inline bars. This makes the correlation quantitative.

## Working rules (credit budget matters)
- Work **one milestone per session**. When a milestone is done, commit, open a PR or push to main as instructed, write a five-line summary, and **stop**. Do not start the next milestone unprompted.
- Before writing code for a milestone, take a quick look at the data. Do not over-engineer.
- If a download is blocked by the network allowlist, say so plainly, list the exact URLs, and stop. Do not try workarounds.
- Prefer small, verifiable steps. "Done" means the check listed for the milestone passes.
- Do not add dependencies beyond the stack above without explaining why.

## Milestones
**M1 — Data acquisition and inspection.**
Run `01_download.py` to fetch geo2bg and the Natural Earth places and roads. Clip everything to a bounding box of about 34°E–60°E, 12°N–33°N. Print a summary: CRS, feature counts, attribute fields, and the unique geology units with their counts. Draft `geology_classes.csv`.
*Done when:* the summary is printed in the session and the CSV draft is committed for owner review.

**M2 — Geology and overlays processing.**
Write `02_geology.py`: apply the CSV (both levels), dissolve by L2, simplify, reproject to EPSG:4326, and export `docs/data/geology.geojson`. Write `03_overlays.py`: select cities (population or scalerank threshold, about 40–80 labels) and major roads, then export GeoJSON.
*Done when:* the files exist, `geology.geojson` is under 8 MB, and a quick matplotlib preview PNG is committed to `notebooks/`.

**M3 — Viewer MVP.**
Build `docs/index.html` with MapLibre, Terrarium terrain plus hillshade, the draped geology fill, roads, city labels, a side legend with class toggles and a Generalized/Detailed (L1/L2) switch with L2 nested under L1, popups showing both levels, and sliders for exaggeration and opacity. Add attribution for all sources.
*Done when:* the site is served locally (`python -m http.server -d docs`), it loads without console errors, a screenshot is taken with Playwright, and no borders are visible.

**M4 — Geology × topography layer.**
Add bookmarks and the tour, plus the per-class elevation stats for L1 and L2 (`04_elevation_stats.py` → `docs/data/elev_stats.json`), shown in the legend for the active level.
*Done when:* every bookmark renders in a screenshot and the stats are shown.

**M5 — Publish.**
Write the README (live link, rebuild steps, sources and licences). Configure GitHub Pages to serve from `/docs` on main, or tell the owner the exact setting to click. Do a mobile-width check.
*Done when:* the owner confirms the Pages URL opens.

## Sources and licences
- USGS OFR 97-470B (Pollastro, Karshbaum & Viger) — public domain; cite the DOI.
- Natural Earth — public domain.
- AWS Terrain Tiles — open data; credit the underlying sources as the dataset documentation requires.
- MapLibre GL JS — BSD-3.
