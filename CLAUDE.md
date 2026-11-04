# Arabia 3D — Geology × Topography of the Arabian Peninsula

## Goal
A static, interactive 3D web map of the Arabian Peninsula states (Saudi Arabia, Kuwait, Bahrain, Qatar, UAE, Oman, Yemen), hosted on GitHub Pages, that anyone can open from a link. Regional-scale geology is coloured and draped over 3D terrain, with city and road overlays. The point of the map is to let a viewer **see how geology correlates with topography**: the Arabian Shield vs. the cover sequence, escarpments, volcanic fields, sand seas and the Oman mountains.

Owner: geoscientist (petrology/geochemistry, Python). Communicate in English. Keep explanations short and technical.

## Hard requirements
- **Static only.** No backend, no build server at runtime, no API keys or tokens. It must work from GitHub Pages.
- **3D terrain** with a vertical-exaggeration control.
- **Geology** coloured by simplified regional class and draped on the terrain, with adjustable opacity.
- **Overlays:** major cities (labels) and major roads.
- **No country borders or admin boundaries anywhere.** That includes not using any third-party basemap that draws them. The coastline is fine.
- **Legend in a side panel.** Each class can be toggled on and off. Clicking a polygon shows a popup with the unit name, age, lithology and source.
- **Regional scale.** Generalise the geology to the eight Level 1 classes below. Fine detail is not wanted; contrasts that line up with relief are.
- Works on desktop and is usable on a phone.

## Stack (defaults — change only with a stated reason)
- **Viewer:** MapLibre GL JS (from cdnjs/unpkg), plain HTML/CSS/JS, no framework, no bundler.
- **Terrain:** AWS Open Data "Terrain Tiles" in Terrarium encoding (`https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png`). They are public and need no key. Use them as a `raster-dem` source for both `terrain` and a `hillshade` layer. Include the attribution the dataset requires.
- **Geology:** USGS Open-File Report 97-470B, "Bedrock geology of the Arabian Peninsula and selected adjacent areas" (geo2bg), DOI 10.3133/ofr97470B. This is public domain, derived from the USGS–Aramco 1963 1:2,000,000 map. Find the data release (USGS ScienceBase or pubs.usgs.gov) and download the shapefile.
- **Cities and roads:** Natural Earth 1:10m `populated_places` and `roads` (public domain). The only use of an admin layer is `admin_0_countries`, as an internal peninsula clip mask; never display or export it.
- **Label glyphs:** a public glyph endpoint, for example `https://demotiles.maplibre.org/font/{fontstack}/{range}.pbf`. If that is unreliable, self-host the glyph PBFs in the repo.
- **Processing:** Python 3.11+, with geopandas, shapely, pyproj, rasterio, numpy, requests. Put the scripts in `scripts/`, numbered in run order. Add an optional exploratory notebook in `notebooks/`, since the owner works in JupyterLab.

## Repository layout
```
scripts/        01_download.py, 02_geology.py, 03_overlays.py, 04_elevation_stats.py,
                geology_classes.csv, polygon_overrides.csv
data/raw/       sources (geo2bg committed; Natural Earth zips gitignored)
data/interim/   clipped layers (gitignored)
data/geology_polygons.csv   per-polygon table: pid + labels (committed)
docs/           the published site (GitHub Pages serves /docs from main)
  index.html  app.js  style.css  data/*.geojson
notebooks/      optional exploration
README.md       what it is, the live link, how to rebuild, sources and licences
```

## Geology classification (owner decisions, 2026-11-04)
geo2bg has a single age attribute, `GLG`. In the peninsula area it contains 27 codes. Classification uses two files in `scripts/`:
- **`geology_classes.csv`**: maps each `GLG` code to `level1_class`, `level1_colour` and an optional `level2_label`, plus `notes`. `H2O` and `U` are `EXCLUDE`.
- **`polygon_overrides.csv`**: per-polygon corrections, with columns `pid, level1_class, level2_label, notes`. A non-empty field replaces the unit-based value. Example: `AG01234,Triassic,,owner: Khuff outcrop`. This is how a request like "polygon X should be Triassic" is applied, and how polygon-only labels such as "Semail ophiolite" are added.

**Level 1 is the only fill scheme.** Eight classes, colours from the reference generalized map:

| Class | Colour | geo2bg units |
|---|---|---|
| Precambrian basement (Arabian Shield) | #E8456B | pC, PzpC |
| Paleozoic | #9DBF95 | Cm, OCm, DSO, D, P, Pz, MzPz |
| Triassic | #8B3A9A | Tr, TrP |
| Jurassic | #2BA6C9 | J, JTr |
| Cretaceous | #6DBE45 | K, KJ, TK |
| Tertiary sedimentary | #EE8E4A | T (Paleocene–Eocene / Oligocene / Miocene–Pliocene are not separable in geo2bg) |
| Cenozoic volcanics | #D9B400 | QTv, Qv, TKv (Yemen traps), TKi, Czi |
| Cenozoic eolian sand and gravel | #F5EFAA | Qe, Qf, Q, Qsk, QT |

**Level 2 is an optional label, not a fill.** It records either a finer age range from the source code (Cambrian-Ordovician, Ordovician-Devonian, Carboniferous-Permian, Permian-Triassic, Triassic-Jurassic, Jurassic-Cretaceous, Cretaceous-Tertiary, Paleozoic-Mesozoic) or a special feature (Harrats, Yemen traps, Sabkha, Eolian sand, Alluvium and gravel, Neogene-Quaternary gravels, Cenozoic intrusives, and later Semail ophiolite via overrides). Polygons with no label have it blank.

**Polygon IDs.** Every polygon has a stable `pid` = `AG` + 5-digit `GEO2BG_ID`. Where the peninsula clip splits a source polygon, the parts get `-a`, `-b`, … (largest first). `01_download.py` writes the committed table `data/geology_polygons.csv` (pid, GEO2BG_ID, GLG, level1_class, level1_colour, level2_label, label_source, area_km2, lon, lat) for review. **pids must survive every later step:** M2 does not dissolve.

**Extent.** Only the Arabian Peninsula states: the GCC (Saudi Arabia, Kuwait, Bahrain, Qatar, UAE, Oman) plus Yemen. The clip mask is (Natural Earth 10m admin-0 polygons of these seven states buffered 0.2° seaward) minus all other countries, so geo2bg's own coastline is kept. The Socotra archipelago is also removed (51.5–55°E, 11–13°N), because geo2bg has no geology there. The admin-0 layer is used **only** to build this mask. It is never exported or drawn. Cities and roads are clipped with the same mask. The landward edge of the data therefore follows the peninsula's outer political boundary (against Jordan and Iraq), while borders between the seven states are never drawn.

Simplify the geometry so that `docs/data/geology.geojson` is **under 8 MB**. Use topology-preserving coverage simplification on the individual polygons (no dissolve), and keep `pid`, `GLG`, `level1_class`, `level1_colour` and `level2_label` on every feature.

**Viewer implications (M3/M4):**
- The legend lists the eight L1 classes, each with an on/off toggle. There is no L1/L2 switch.
- **Popups** show the `pid` (so the owner can quote it in correction requests), the L1 class, the L2 label if present, the `GLG` code, age, lithology note and source citation.
- **Elevation stats** are computed per L1 class. Per-L2-label stats are optional, for labelled features such as harrats and sabkha.

## "Geology × topography" features
- **Bookmarks / tour:** 6–8 camera presets with flyTo, pitch and bearing, each with a two-sentence caption. Suggested stops: the Hijaz–Asir escarpment and the Shield; Harrat Rahat / Harrat Khaybar; the Tuwaiq escarpment; the Rub' al Khali; the Hajar Mountains and the Semail ophiolite; the Yemen highlands and traps; Dhofar; the UAE coastal sabkhas and Musandam.
- **Elevation stats per class:** precompute the min, median and max elevation per L1 class (optionally also per L2 label), from Terrarium tiles sampled at a low zoom (z6–7). Show them in the legend as small inline bars. This makes the correlation quantitative.

## Working rules (credit budget matters)
- Work **one milestone per session**. When a milestone is done, commit, open a PR or push to main as instructed, write a five-line summary, and **stop**. Do not start the next milestone unprompted.
- Before writing code for a milestone, take a quick look at the data. Do not over-engineer.
- If a download is blocked by the network allowlist, say so plainly, list the exact URLs, and stop. Do not try workarounds.
- Prefer small, verifiable steps. "Done" means the check listed for the milestone passes.
- Do not add dependencies beyond the stack above without explaining why.

## Milestones
**M1 — Data acquisition and inspection.**
Run `01_download.py` to fetch the Natural Earth places, roads and admin-0 layers (geo2bg is already in the repo). Clip everything to the peninsula mask, assign polygon `pid`s, apply `geology_classes.csv` and `polygon_overrides.csv`, and write `data/geology_polygons.csv`. Print a summary: CRS, feature counts, attribute fields, and unit, L1 and L2 counts and areas.
*Done when:* the summary is printed in the session and the CSV draft is committed for owner review.

**M2 — Geology and overlays processing.**
Write `02_geology.py`: read `data/interim/geology_peninsula.gpkg` (pids and labels from M1), apply coverage simplification without dissolving, and export `docs/data/geology.geojson` in EPSG:4326 with the pid and label fields. Write `03_overlays.py`: select cities (population or scalerank threshold, about 40–80 labels) and major roads, then export GeoJSON.
*Done when:* the files exist, `geology.geojson` is under 8 MB, and a quick matplotlib preview PNG is committed to `notebooks/`.

**M3 — Viewer MVP.**
Build `docs/index.html` with MapLibre, Terrarium terrain plus hillshade, the draped geology fill, roads, city labels, a side legend with L1 class toggles, popups showing pid, L1, L2 label and GLG, and sliders for exaggeration and opacity. Add attribution for all sources.
*Done when:* the site is served locally (`python -m http.server -d docs`), it loads without console errors, a screenshot is taken with Playwright, and no borders are visible.

**M4 — Geology × topography layer.**
Add bookmarks and the tour, plus the per-L1-class elevation stats (`04_elevation_stats.py` → `docs/data/elev_stats.json`), shown in the legend.
*Done when:* every bookmark renders in a screenshot and the stats are shown.

**M5 — Publish.**
Write the README (live link, rebuild steps, sources and licences). Configure GitHub Pages to serve from `/docs` on main, or tell the owner the exact setting to click. Do a mobile-width check.
*Done when:* the owner confirms the Pages URL opens.

## Sources and licences
- USGS OFR 97-470B (Pollastro, Karshbaum & Viger) — public domain; cite the DOI.
- Natural Earth — public domain.
- AWS Terrain Tiles — open data; credit the underlying sources as the dataset documentation requires.
- MapLibre GL JS — BSD-3.
