"""M1: fetch Natural Earth layers, clip all inputs to the Arabian Peninsula states (GCC + Yemen), assign polygon IDs, print a summary.

geo2bg (USGS OFR 97-470B) is already in the repo at data/raw/geology/ and is not downloaded.

Peninsula mask: the Natural Earth admin-0 layer is used ONLY to build the clip mask here. It is never
exported or displayed. Mask = (peninsula states buffered 0.2 deg seaward) minus (all other countries).
The buffer keeps geo2bg's own coastline intact where it differs from Natural Earth's.

Polygon IDs: pid = "AG" + GEO2BG_ID (5 digits). If the mask splits a source polygon, the parts
get a suffix -a, -b, ... (largest first). IDs are stable while the source data and mask stay the same.

Labels: scripts/geology_classes.csv maps GLG -> level1_class (+ colour) and an optional level2_label.
scripts/polygon_overrides.csv then overrides individual polygons by pid.

OSM roads: highway=motorway|trunk|primary from OpenStreetMap (ODbL, (c) OpenStreetMap contributors).
Overpass and Geofabrik are not reachable from the cloud build environment, so the raw data are Geofabrik
extracts (gcc-states, yemen; 2026-11-03) filtered locally to these three classes and committed to
data/raw/osm/ (8.5 MB). To refresh: download https://download.geofabrik.de/asia/gcc-states-latest.osm.pbf
and .../yemen-latest.osm.pbf, then run
  python scripts/01_download.py --osm-extract <dir with the full .osm.pbf files> <YYMMDD>
and update OSM_FILES. Ways are de-duplicated by OSM id (the two extracts overlap at the border) and
clipped with the same peninsula mask.

Outputs:
  data/interim/*.gpkg            clipped layers (gitignored); geology_peninsula.gpkg has pid + labels
  data/geology_polygons.csv      committed per-polygon table (no geometry) for review/edits by pid
"""
import sys
from pathlib import Path

import geopandas as gpd
import osmium
import shapely
import pandas as pd
import requests
from shapely.geometry import box

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
NE_DIR = RAW / "naturalearth"
INTERIM = ROOT / "data" / "interim"
GEO_SHP = RAW / "geology" / "geo2bg.shp"
CLASSES = ROOT / "scripts" / "geology_classes.csv"
OVERRIDES = ROOT / "scripts" / "polygon_overrides.csv"
POLY_TABLE = ROOT / "data" / "geology_polygons.csv"

BBOX = (34.0, 12.0, 60.0, 33.0)  # lon_min, lat_min, lon_max, lat_max (EPSG:4326)
STATES = ["SAU", "KWT", "BHR", "QAT", "ARE", "OMN", "YEM"]  # GCC + Yemen
COAST_BUFFER_DEG = 0.2
# Areas removed from the mask: Socotra archipelago (Yemen) has no geo2bg coverage
EXCLUDE_BOXES = {"Socotra archipelago": (51.5, 11.0, 55.0, 13.0)}
MIN_PART_KM2 = 0.1  # drop clip slivers smaller than this
EQUAL_AREA = 6933

OSM_DIR = RAW / "osm"
OSM_FILES = ["gcc_roads_261103.osm.pbf", "yemen_roads_261103.osm.pbf"]
OSM_CLASSES = ("motorway", "trunk", "primary")
OSM_TAGS = {"ref": "ref", "int_ref": "int_ref", "name": "name", "name_en": "name:en", "name_ar": "name:ar"}

NE_URLS = {
    "populated_places": "https://naciscdn.org/naturalearth/10m/cultural/ne_10m_populated_places.zip",
    "roads": "https://naciscdn.org/naturalearth/10m/cultural/ne_10m_roads.zip",
    "admin_0_countries": "https://naciscdn.org/naturalearth/10m/cultural/ne_10m_admin_0_countries.zip",
}


def download(url: str, dest: Path) -> Path:
    if dest.exists() and dest.stat().st_size > 0:
        print(f"  cached  {dest.relative_to(ROOT)}")
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"  GET     {url}")
    with requests.get(url, stream=True, timeout=120) as r:
        r.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in r.iter_content(1 << 20):
                f.write(chunk)
    return dest


def peninsula_mask(countries_zip: Path):
    c = gpd.read_file(f"zip://{countries_zip}").to_crs(4326)
    c = c[c.intersects(box(*BBOX))]
    keep = c[c["ADM0_A3"].isin(STATES)]
    others = c[~c["ADM0_A3"].isin(STATES)]
    print(f"States in mask: {sorted(keep['ADMIN'])}")
    print(f"Excluded neighbours: {sorted(others['ADMIN'])}")
    mask = keep.union_all().buffer(COAST_BUFFER_DEG).difference(others.union_all())
    for name, b in EXCLUDE_BOXES.items():
        print(f"Removed from mask: {name} {b}")
        mask = mask.difference(box(*b))
    return mask.intersection(box(*BBOX))


def osm_extract(src_dir: Path, date: str) -> None:
    """Filter full Geofabrik extracts to OSM_CLASSES ways (+ their nodes) into data/raw/osm/."""
    road_filter = osmium.filter.TagFilter(*[("highway", c) for c in OSM_CLASSES])
    OSM_DIR.mkdir(parents=True, exist_ok=True)
    for region, short in (("gcc-states", "gcc"), ("yemen", "yemen")):
        src = next(Path(src_dir).glob(f"{region}-*.osm.pbf"))
        dst = OSM_DIR / f"{short}_roads_{date}.osm.pbf"
        with osmium.BackReferenceWriter(str(dst), ref_src=str(src), overwrite=True) as w:
            for way in osmium.FileProcessor(str(src), osmium.osm.WAY).with_filter(road_filter):
                w.add(way)
        print(f"  {src.name} -> {dst.relative_to(ROOT)} ({dst.stat().st_size / 1e6:.1f} MB)")


def read_osm_roads() -> gpd.GeoDataFrame:
    wkb = osmium.geom.WKBFactory()
    rows, n_bad = {}, 0
    for fname in OSM_FILES:
        fp = osmium.FileProcessor(str(OSM_DIR / fname), osmium.osm.NODE | osmium.osm.WAY).with_locations()
        for w in fp:
            if not w.is_way() or w.id in rows or w.tags.get("highway") not in OSM_CLASSES:
                continue
            try:
                geom = shapely.from_wkb(wkb.create_linestring(w))
            except (osmium.InvalidLocationError, RuntimeError):
                n_bad += 1
                continue
            rows[w.id] = {"osm_id": w.id, "highway": w.tags["highway"],
                          **{k: w.tags.get(t, "") for k, t in OSM_TAGS.items()}, "geometry": geom}
    if n_bad:
        print(f"Skipped {n_bad} OSM ways with missing node locations")
    return gpd.GeoDataFrame(list(rows.values()), crs=4326)


def area_km2(gdf: gpd.GeoDataFrame) -> pd.Series:
    return gdf.to_crs(EQUAL_AREA).area / 1e6


def summary(name: str, raw: gpd.GeoDataFrame, clipped: gpd.GeoDataFrame) -> None:
    print(f"\n=== {name} ===")
    print(f"CRS:      {raw.crs.to_string() if raw.crs else None}")
    print(f"Features: {len(raw)} total -> {len(clipped)} in peninsula mask")
    print(f"Geometry: {sorted(clipped.geom_type.unique())}")
    print(f"Fields:   {[c for c in raw.columns if c != 'geometry']}")


def build_geology(mask) -> gpd.GeoDataFrame:
    geo = gpd.read_file(GEO_SHP).to_crs(4326)
    classes = pd.read_csv(CLASSES, dtype=str).fillna("")
    missing = set(geo["GLG"]) - set(classes["source_unit"])
    assert not missing, f"GLG units missing from {CLASSES.name}: {missing}"

    g = gpd.clip(geo, mask)
    g = g[g.geom_type.isin(["Polygon", "MultiPolygon"])].explode(index_parts=False)
    g["area_km2"] = area_km2(g)
    n_sliver = int((g["area_km2"] < MIN_PART_KM2).sum())
    g = g[g["area_km2"] >= MIN_PART_KM2].copy()

    # pid: AG<GEO2BG_ID>, plus -a/-b/... (largest part first) where the clip split a polygon
    g = g.sort_values(["GEO2BG_ID", "area_km2"], ascending=[True, False])
    part = g.groupby("GEO2BG_ID").cumcount()
    nparts = g.groupby("GEO2BG_ID")["GLG"].transform("size")
    g["pid"] = "AG" + g["GEO2BG_ID"].astype(int).map("{:05d}".format)
    g.loc[nparts > 1, "pid"] += "-" + part[nparts > 1].map(lambda i: chr(97 + i))
    assert g["pid"].is_unique

    g = g.merge(classes[["source_unit", "level1_class", "level2_label"]],
                left_on="GLG", right_on="source_unit", how="left").drop(columns="source_unit")
    g["label_source"] = "unit"

    ov = pd.read_csv(OVERRIDES, dtype=str).fillna("")
    if len(ov):
        unknown = set(ov["pid"]) - set(g["pid"])
        assert not unknown, f"Unknown pids in {OVERRIDES.name}: {unknown}"
        valid_l1 = set(classes["level1_class"]) - {"EXCLUDE"}
        bad = set(ov.loc[ov["level1_class"] != "", "level1_class"]) - valid_l1
        assert not bad, f"Unknown level1_class in {OVERRIDES.name}: {bad}"
        for _, r in ov.iterrows():
            i = g["pid"] == r["pid"]
            for col in ("level1_class", "level2_label"):
                if r[col]:
                    g.loc[i, col] = r[col]
            g.loc[i, "label_source"] = "override"

    n_excl = int((g["level1_class"] == "EXCLUDE").sum())
    g = g[g["level1_class"] != "EXCLUDE"]
    colours = classes.drop_duplicates("level1_class").set_index("level1_class")["level1_colour"]
    g["level1_colour"] = g["level1_class"].map(colours)
    pts = g.representative_point()
    g["lon"], g["lat"] = pts.x.round(4), pts.y.round(4)
    g["area_km2"] = g["area_km2"].round(2)
    print(f"\nDropped {n_sliver} clip slivers < {MIN_PART_KM2} km2 and {n_excl} EXCLUDE polygons")
    cols = ["pid", "GEO2BG_ID", "GLG", "level1_class", "level1_colour", "level2_label",
            "label_source", "area_km2", "lon", "lat"]
    return gpd.GeoDataFrame(g[cols + ["geometry"]], crs=4326).sort_values("pid")


def main() -> None:
    print("Downloading Natural Earth layers")
    zips = {k: download(u, NE_DIR / Path(u).name) for k, u in NE_URLS.items()}
    INTERIM.mkdir(parents=True, exist_ok=True)

    mask = peninsula_mask(zips["admin_0_countries"])

    # Geology
    geo_raw = gpd.read_file(GEO_SHP)
    geo = build_geology(mask)
    summary("geo2bg (USGS OFR 97-470B), clipped + exploded", geo_raw, geo)
    geo.to_file(INTERIM / "geology_peninsula.gpkg", driver="GPKG")
    pd.DataFrame(geo.drop(columns="geometry")).to_csv(POLY_TABLE, index=False)

    print("\nGLG units in peninsula area (polygons, km2):")
    print(geo.groupby("GLG").agg(polygons=("pid", "size"), area_km2=("area_km2", "sum"))
          .sort_values("area_km2", ascending=False).round(0).to_string())
    print("\nLevel 1 classes:")
    print(geo.groupby("level1_class").agg(polygons=("pid", "size"), area_km2=("area_km2", "sum"))
          .sort_values("area_km2", ascending=False).round(0).to_string())
    print("\nLevel 2 labels (blank = no label):")
    print(geo.groupby(["level1_class", "level2_label"], dropna=False)
          .agg(polygons=("pid", "size"), area_km2=("area_km2", "sum")).round(0).to_string())

    # Natural Earth overlays, same mask
    for key in ("populated_places", "roads"):
        gdf = gpd.read_file(f"zip://{zips[key]}")
        gdf_c = gpd.clip(gdf.to_crs(4326), mask)
        summary(f"Natural Earth 10m {key}", gdf, gdf_c)
        if key == "populated_places":
            print("SCALERANK counts:", gdf_c["SCALERANK"].value_counts().sort_index().to_dict())
        else:
            print("type counts:", gdf_c["type"].value_counts().to_dict())
        gdf_c.to_file(INTERIM / f"{key}_peninsula.gpkg", driver="GPKG")

    # OSM main roads, same mask
    osm = read_osm_roads()
    osm_c = gpd.clip(osm, mask)
    osm_c = osm_c[osm_c.geom_type.isin(["LineString", "MultiLineString"])]
    summary(f"OpenStreetMap roads ({', '.join(OSM_FILES)})", osm, osm_c)
    km = osm_c.to_crs(EQUAL_AREA).length / 1e3
    print("highway (ways, km):", {h: (int((osm_c.highway == h).sum()), round(km[osm_c.highway == h].sum()))
                                  for h in OSM_CLASSES})
    print(f"ways with ref: {(osm_c.ref != '').mean():.0%}, name:en: {(osm_c.name_en != '').mean():.0%}, "
          f"name:ar: {(osm_c.name_ar != '').mean():.0%}")
    osm_c.to_file(INTERIM / "osm_roads_peninsula.gpkg", driver="GPKG")

    print(f"\nWrote {INTERIM.relative_to(ROOT)}/*_peninsula.gpkg and {POLY_TABLE.relative_to(ROOT)}")


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "--osm-extract":
        osm_extract(Path(sys.argv[2]), sys.argv[3])
    else:
        main()
