# Arabia 3D — Geology × Topography of the Arabian Peninsula

A generalized geological map of the Arabian Peninsula, draped over 3D terrain in a static web viewer. It is made for KFUPM (King Fahd University of Petroleum & Minerals). The aim is to show how regional geology lines up with topography: the Arabian Shield against the Phanerozoic cover, the Tuwaiq escarpment, the harrats, the sand seas, and the Hajar and Yemen highlands.

**Live map:** not published yet (milestone M5).

## Status

| Milestone | State |
|---|---|
| M1 — data acquisition, clipping, classification, polygon IDs | done |
| M2 — simplified GeoJSON for the web | done |
| M3 — MapLibre 3D viewer | to do |
| M4 — tour bookmarks and per-class elevation stats | to do |
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

`03_overlays.py` writes `docs/data/cities.geojson` and `docs/data/roads.geojson`. Cities: all 73 Natural Earth places in the extent (Hawalli dropped as part of Kuwait City), named in regional English usage (Madinah, Jazan, Sohar, Sana'a, …) with curated Arabic names, both from [`scripts/cities.csv`](scripts/cities.csv); edit that file to rename or drop a city. Roads: OpenStreetMap `highway=motorway|trunk|primary` (~98,800 km), merged per (class, `ref`), or per (class, name) where there is no ref, giving 1,400 features (1.5 MB). Fields: `class`, `ref`, `name_en`, `name_ar`. Geometry is simplified at 0.001° (~100 m), parts under 0.5 km are dropped and coordinates are rounded to 4 decimals. Natural Earth roads were used before. They were dropped because they are generalized for 1:10M (off by 1–3 km), miss recent highways and misclassify trunk routes as "Unknown". The script still prints the NE roads with no OSM motorway/trunk/primary within 5 km, as a check.

The OSM data are Geofabrik extracts (`gcc-states`, `yemen`, 2026-11-03) filtered to the three road classes and committed to `data/raw/osm/` (8.5 MB). Overpass and Geofabrik are not reachable from the cloud build environment. To refresh, download https://download.geofabrik.de/asia/gcc-states-latest.osm.pbf and https://download.geofabrik.de/asia/yemen-latest.osm.pbf, then run `python scripts/01_download.py --osm-extract <download dir> <YYMMDD>` and update `OSM_FILES` in `01_download.py`.

`notebooks/m2_preview.py` renders `notebooks/m2_preview.png`.

## Repository layout

```
scripts/      01_download.py, 02_geology.py, 03_overlays.py, geology_classes.csv, cities.csv, polygon_overrides.csv
data/raw/     geo2bg shapefile and OSM road extracts in osm/ (committed); Natural Earth zips (gitignored)
data/interim/ clipped layers (gitignored)
data/geology_polygons.csv   one row per polygon: pid, unit, labels, area, location
docs/data/    web layers: geology.geojson, cities.geojson, roads.geojson
docs/         web viewer (from M3)
notebooks/    m2_preview.py / .png
```

## Sources and licences

- **Geology:** Pollastro, R.M., 1998, *Bedrock geology of the Arabian Peninsula and selected adjacent areas (geo2bg)*, digital dataset in Pollastro, R.M., Karshbaum, A.S., and Viger, R.J., 1999, *Map showing geology, oil and gas fields and geologic provinces of the Arabian Peninsula*, USGS Open-File Report 97-470-B, https://doi.org/10.3133/ofr97470B. Public domain. Derived from the USGS–ARAMCO 1:2,000,000 geologic map (1963).
- **Cities, clip mask:** Natural Earth 1:10m, public domain.
- **Roads:** © OpenStreetMap contributors, https://www.openstreetmap.org/copyright. Extracts from Geofabrik (download.geofabrik.de), 2026-11-03. `docs/data/roads.geojson` and `data/raw/osm/*.osm.pbf` are derived from OpenStreetMap and licensed under the [Open Database License (ODbL) 1.0](https://opendatacommons.org/licenses/odbl/1-0/). You may copy, share and adapt them, provided you credit "© OpenStreetMap contributors" and share any public adapted database under the ODbL. The viewer must show this credit in its map attribution. The rest of the repository keeps its own licence.
- **Terrain (from M3):** AWS Open Data Terrain Tiles (Terrarium).
- **Viewer (from M3):** MapLibre GL JS, BSD-3.
