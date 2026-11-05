# Arabia 3D — Geology × Topography of the Arabian Peninsula

A generalized geological map of the Arabian Peninsula, draped over 3D terrain in a static web viewer. It is made for KFUPM (King Fahd University of Petroleum & Minerals). The aim is to show how regional geology lines up with topography: the Arabian Shield against the Phanerozoic cover, the Tuwaiq escarpment, the harrats, the sand seas, and the Hajar and Yemen highlands.

**Live map:** not published yet (milestone M5).

## Status

| Milestone | State |
|---|---|
| M1 — data acquisition, clipping, classification, polygon IDs | done |
| M2 — simplified GeoJSON for the web | done |
| M3 — MapLibre 3D viewer | done |
| M4 — tour bookmarks and per-class elevation stats | done |
| M5 — publish on GitHub Pages | to do |

## Extent

The map covers Saudi Arabia, Kuwait, Bahrain, Qatar, the UAE, Oman and Yemen. Neighbouring countries are clipped out. The Socotra archipelago is removed because the source map has no geology there. No country borders are drawn. The Natural Earth country outlines are used only internally, to build the clip mask.

## Geology classification

Source: USGS OFR 97-470B (geo2bg), whose only geological attribute is the age code `GLG`. Codes are mapped in [`scripts/geology_classes.csv`](scripts/geology_classes.csv).

**Level 1** is the map colour, with eight classes following a published generalized geologic map of the peninsula:

| Class | Colour | geo2bg codes |
|---|---|---|
| Precambrian basement (Arabian Shield) | `#E8456B` | pC, PzpC |
| Paleozoic | `#9DBF95` | Cm, OCm, DSO, D, P, Pz, MzPz |
| Triassic | `#8B3A9A` | Tr, TrP |
| Jurassic | `#2BA6C9` | J, JTr |
| Cretaceous | `#6DBE45` | K, KJ, TK |
| Paleogene-Neogene sedimentary | `#EE8E4A` | T |
| Cenozoic volcanics | `#D9B400` | QTv, Qv, TKv, TKi, Czi |
| Neogene-Quaternary surficial deposits | `#F5EFAA` | Qe, Qf, Q, Qsk, QT |

**Level 2** is an optional label, not a colour. It gives either a finer age range taken from the source code (for example Cambrian-Ordovician, Permian-Triassic) or a named feature (Harrats, Yemen traps, Sabkha, Eolian sand, Alluvium and gravel, Neogene-Quaternary gravels, Cenozoic intrusives).

Limits of the source data:
- geo2bg does not subdivide its "Tertiary" unit (T), so Paleocene–Eocene, Oligocene and Miocene–Pliocene are mapped together as Paleogene-Neogene. "Tertiary" is no longer a formal ICS unit, so it is not used in class names.
- The surficial class is mostly alluvium, gravel and sabkha as well as eolian sand; Level 2 labels separate them. It is Neogene-Quaternary because geo2bg QT gravels are included.
- The Semail ophiolite and Hawasina allochthon are not separated from the Cretaceous. This is deliberate, since this is a generalized map.

## Polygon IDs and corrections

Every polygon has a stable ID, `pid` = `AG` + the 5-digit geo2bg `GEO2BG_ID`. Where the clip mask cuts a source polygon, the pieces get `-a`, `-b`, and so on. All polygons and their labels are listed in [`data/geology_polygons.csv`](data/geology_polygons.csv).

To correct a single polygon, add a row to [`scripts/polygon_overrides.csv`](scripts/polygon_overrides.csv) and rebuild:

```
pid,level1_class,level2_label,notes
AG01234,Triassic,,Khuff outcrop
```

Empty fields keep the value that comes from the polygon's unit. The script stops if a `pid` or class name doesn't exist.

## Rebuild

Requires Python 3.11+.

```bash
pip install geopandas "shapely>=2.2" pyproj pyogrio requests matplotlib "osmium>=4.0"
```

```bash
python scripts/01_download.py
```

```bash
python scripts/02_geology.py
```

```bash
python scripts/03_overlays.py
```

`01_download.py` downloads the Natural Earth layers into `data/raw/naturalearth/`, reads the OpenStreetMap road extracts in `data/raw/osm/`, and writes the clipped layers to `data/interim/` (naturalearth and interim are gitignored). It regenerates `data/geology_polygons.csv` and prints a summary. `02_geology.py` cleans the polygon coverage (GEOS CoverageCleaner, so shared edges match vertex-for-vertex), applies topology-preserving coverage simplification (tolerance 0.004°, no dissolve, every `pid` kept), rounds coordinates to 4 decimals and writes `docs/data/geology.geojson` (~7 MB). It stops if the pid set differs from `data/geology_polygons.csv`, if any geometry is empty or invalid, or if gaps or overlaps appear. Shapely ≥ 2.2 (GEOS ≥ 3.14) is needed for `coverage_clean`.

**Mountain-front contacts adjusted to the terrain.** geo2bg was drawn at 1:2,000,000 in 1963. At mountain fronts the mapped bedrock/alluvium contact is typically 1–2 km from the foot of the slope in the SRTM-based terrain, so in 3D the colours spill onto the plain or up the slope. There is no systematic shift that a single nudge or warp could fix (`notebooks/alignment_check.py`). The offset is local (`notebooks/front_offsets.py`).

`02_geology.py` therefore moves these contacts, and only these, with `scripts/contacts.py` (parameters at the top of that file):
- **Which contacts:** shared edges with bedrock (any class except the surficial one) on one side and alluvium, gravel or sabkha on the other. Eolian sand is excluded because dunes have their own slopes.
- **Where:** four areas — Hajar and Musandam, Asir and Tihamah, Yemen highlands, Dhofar.
- **Finding the foot:** every 300 m along a contact, a z10 slope profile (~140 m pixels) is taken across it. The contact moves to the foot of the slope only where there is a clear front: ≥ 8° within 0.3–1.5 km on the bedrock side and ≤ 6° within 0.3–1.5 km on the plain side. Flat plateaux and pediments are not touched.
- **Smoothing:** moves are smoothed along the contact, capped at 5 km, and fade to zero away from measured stretches and at junctions. Junctions never move.
- **Safety:** a move that would cross or swallow another boundary is scaled down or dropped.
- **Result:** polygons are rebuilt from their edges, so the coverage stays gap- and overlap-free and every pid is kept. The 02 checks run on the result.
- **Not adjusted:** contacts between two bedrock units (e.g. Jurassic/Cretaceous) and harrat edges, because slope does not define them.
- **Output:** 115 contacts moved in 108 polygons, and 1,241 km² reassigned between bedrock and alluvium (mostly bedrock → alluvium, where the mapped bedrock ran out onto the plain). In Asir the main escarpment lies inside the Precambrian in geo2bg (the Shield is mapped down to a narrow coastal strip), so only isolated ridges changed there.
- **Flag:** adjusted polygons carry `contact_adjusted: 1`, and their popup says so. The unadjusted version is kept in `data/interim/geology_web_unadjusted.gpkg`. Run `python scripts/02_geology.py --no-adjust` to skip the step.
- **Before/after maps:** `notebooks/contacts/*.png`, made by `python notebooks/contacts_before_after.py` — an overview and two close-ups per area. Each has Before, After and Change panels on hillshade: red = bedrock → alluvium, blue = alluvium → bedrock, dashed = old contact, solid = new contact.

`03_overlays.py` writes `docs/data/cities.geojson` and `docs/data/roads.geojson`. Cities: all 73 Natural Earth places in the extent (Hawalli dropped as part of Kuwait City), named in regional English usage (Madinah, Jazan, Sohar, Sana'a, …) with curated Arabic names, both from [`scripts/cities.csv`](scripts/cities.csv); edit that file to rename or drop a city. Roads: OpenStreetMap `highway=motorway|trunk|primary` (~98,800 km), merged per (class, `ref`), or per (class, name) where there is no ref, giving 1,400 features (1.5 MB). Fields: `class`, `ref`, `name_en`, `name_ar`. Geometry is simplified at 0.001° (~100 m), parts under 0.5 km are dropped and coordinates are rounded to 4 decimals. Natural Earth roads were used before. They were dropped because they are generalized for 1:10M (off by 1–3 km), miss recent highways and misclassify trunk routes as "Unknown". The script still prints the NE roads with no OSM motorway/trunk/primary within 5 km, as a check.

The OSM data are Geofabrik extracts (`gcc-states`, `yemen`, 2026-11-03) filtered to the three road classes and committed to `data/raw/osm/` (8.5 MB). Overpass and Geofabrik are not reachable from the cloud build environment. To refresh, download https://download.geofabrik.de/asia/gcc-states-latest.osm.pbf and https://download.geofabrik.de/asia/yemen-latest.osm.pbf, then run `python scripts/01_download.py --osm-extract <download dir> <YYMMDD>` and update `OSM_FILES` in `01_download.py`.

`05_units.py` writes `docs/data/units.json` from `scripts/geology_classes.csv`: the legend classes (order, colours, codes) and, per `GLG` code, the age range and a short generalized lithology note shown in the popups. geo2bg has no lithology attribute, so these notes are a regional summary kept in the script; edit them there and rerun.

```bash
python scripts/05_units.py
```

Elevation statistics per geology class (needs `rasterio` and `numpy` in addition):

```bash
pip install rasterio numpy
```

```bash
python scripts/04_elevation_stats.py
```

`04_elevation_stats.py` downloads the 90 AWS Terrarium tiles at zoom 7 that cover the geology (cached in `data/interim/terrarium/`). It decodes elevation as R×256 + G + B/256 − 32768 and mosaics them on their native EPSG:3857 grid (~1.22 km/px). It then rasterizes `docs/data/geology.geojson` onto the same grid (a pixel belongs to the polygon containing its centre) and computes min, p10, median, p90, max, pixel count and the number of pixels below 0 m, per Level 1 class and per Level 2 label. Each pixel counts once: large polygons weigh more and there is no per-polygon averaging. Negative values (coastal pixels that fall on bathymetry) are kept and counted. Web-Mercator pixels shrink towards the north (cos lat, 0.97 at 13°N, 0.85 at 32°N); this is ignored. The result is `docs/data/elev_stats.json`, which the legend draws as box plots on a shared 0–3,700 m scale. The script prints a table and three sanity checks. The Sabkha check (median near 0 m) fails because the inland sabkhas (Umm as Samim, landward Sabkha Matti, Rub' al Khali interdune flats, Al Jafr) lift the median to ~56 m; coastal sabkhas sit at 0–10 m.

`notebooks/m2_preview.py` renders `notebooks/m2_preview.png`.

## Repository layout

```
scripts/      01_download.py, 02_geology.py (+ contacts.py), 03_overlays.py, 04_elevation_stats.py, 05_units.py, geology_classes.csv, cities.csv, polygon_overrides.csv
data/raw/     geo2bg shapefile and OSM road extracts in osm/ (committed); Natural Earth zips (gitignored)
data/interim/ clipped layers (gitignored)
data/geology_polygons.csv   one row per polygon: pid, unit, labels, area, location
docs/data/    web layers: geology.geojson, cities.geojson, roads.geojson, units.json, elev_stats.json
docs/         web viewer: index.html, app.js, style.css, favicon.svg (+ PNGs), preview.png
notebooks/    m2_preview.py / .png, m3_*.png viewer screenshots, m4_screenshots.py / m4_*.png tour and legend check,
              ui_check.py / ui_*.png interface check, make_preview.py (link-preview card),
              alignment_check.py, front_offsets.py (geology vs terrain diagnostics),
              contacts_before_after.py / contacts/*.png (contact adjustment maps)
```

## Viewer

`docs/` is the whole site: `index.html`, `app.js`, `style.css` and `data/`. It uses MapLibre GL JS 5.6.0 from unpkg, with no build step and no basemap (plain background, so no third-party borders). Terrain and hillshade come from the AWS Terrarium tiles; label glyphs (Noto Sans) from `demotiles.maplibre.org`. To view it locally:

```bash
python -m http.server -d docs
```

Then open http://localhost:8000. The map loads ~8.5 MB of GeoJSON uncompressed (geology 7.0 MB, roads 1.5 MB), ~2.2 MB gzipped as GitHub Pages serves it. Screenshots of the M3 check are in `notebooks/m3_*.png`.

The legend shows, per class, an elevation box plot (line = min–max, box = p10–p90, tick = median; hover for numbers). The **Tour** section has eight camera presets (Hijaz–Asir escarpment, Harrat Rahat/Khaybar, Tuwaiq, Rub' al Khali, Hajar, Yemen highlands, Dhofar, UAE sabkhas and Musandam), each with a two-sentence caption. **Play tour** steps through them (~8 s per stop); any drag or zoom stops it, and **Home** returns to the peninsula view. Cameras and captions are in the `STOPS` array at the top of the tour section in `docs/app.js`. Each stop also has `marks`, shown only while that stop is active: red **flags** on named summits (Jabal Sawda, Jabal Shams, Jabal an-Nabi Shu'ayb, Jabal Samhan, Jebel Harim; positions are the z7 DEM maxima near each summit, heights are the commonly quoted values), **area labels** (Arabian Shield, Tihamah, the harrats, Jabal Akhdar and Saih Hatat windows, Semail ophiolite, Yemen traps, Musandam and others), a dark **outline** of the featured geology polygons (harrats, Jurassic outcrop, Oman windows, Yemen traps, sabkhas; a MapLibre filter on `geology.geojson`) and, for stops 1 and 3, a dashed red **escarpment trace**. The traces were derived from the z7 Terrarium mosaic: at each 0.25° of latitude, the steepest eastward rise over ~5–7 km (inside the Jurassic outcrop for Tuwaiq, 20.0–25.25°N; between 41° and 43.6°E for Asir, 18.0–20.25°N). They are approximate, at the ~1–5 km level. Flags and area labels are DOM markers, so they stand upright on the terrain and are never hidden by terrain occlusion. To add or move one, edit `marks` in `STOPS`. `notebooks/m4_screenshots.py` (Python Playwright, with the site served on port 8000) reshoots `notebooks/m4_*.png`.

Interface:
- **First view:** the whole peninsula (flatter camera on phones), with an intro card and a **Take the tour** button. While a stop is shown, its caption box has **Stop tour** and **Home**.
- **Side panel:** collapsible sections. Geology is open; Tour, Display (exaggeration and opacity), Overlays and About start folded.
- **Legend bars:** tap or click a bar to show its numbers (also works on phones, where hover tooltips don't).
- **Cursor readout** (bottom left; tap on phones): latitude, longitude and elevation. The elevation is decoded from the Terrarium tile under the cursor (z7–z12, depending on zoom), so it is in true metres whatever the exaggeration slider says.
- **Loading message** until the geology layer is drawn.
- **About:** author and links, source code, dedication, a one-line disclaimer, data credits and a "Last updated" date. Update the date in `docs/index.html` by hand when you publish changes.
- **Icon:** `docs/favicon.svg` is the peninsula outline (simplified from `geology.geojson`) filled with concentric bands in the Level 1 colours, echoing the cover belts arcing around the Shield. `favicon-32.png` and `apple-touch-icon.png` are rendered from it.
- **Link preview:** `docs/preview.png` (1200×630, a flat view of the whole map) is the `og:image` card shown when the link is shared. The meta tags in `docs/index.html` point to the GitHub Pages address, so the card appears once Pages is live. Regenerate it with `python notebooks/make_preview.py` (site served on port 8000).

`notebooks/ui_check.py` checks the above in Playwright (desktop and phone), writes `notebooks/ui_*.png` and prints any console errors.

## Sources and licences

- **Geology:** Pollastro, R.M., 1998, *Bedrock geology of the Arabian Peninsula and selected adjacent areas (geo2bg)*, digital dataset in Pollastro, R.M., Karshbaum, A.S., and Viger, R.J., 1999, *Map showing geology, oil and gas fields and geologic provinces of the Arabian Peninsula*, USGS Open-File Report 97-470-B, https://doi.org/10.3133/ofr97470B. Public domain. Derived from the USGS–ARAMCO 1:2,000,000 geologic map (1963).
- **Cities, clip mask:** Natural Earth 1:10m, public domain.
- **Roads:** © OpenStreetMap contributors, https://www.openstreetmap.org/copyright. Extracts from Geofabrik (download.geofabrik.de), 2026-11-03. `docs/data/roads.geojson` and `data/raw/osm/*.osm.pbf` are derived from OpenStreetMap and licensed under the [Open Database License (ODbL) 1.0](https://opendatacommons.org/licenses/odbl/1-0/). You may copy, share and adapt them, provided you credit "© OpenStreetMap contributors" and share any public adapted database under the ODbL. The viewer must show this credit in its map attribution. The rest of the repository keeps its own licence.
- **Terrain (from M3):** AWS Open Data Terrain Tiles (Terrarium).
- **Viewer (from M3):** MapLibre GL JS, BSD-3.
