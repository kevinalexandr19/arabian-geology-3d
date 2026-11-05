"""M2: simplify the peninsula geology for the web, without dissolving, and export GeoJSON.

Input:  data/interim/geology_peninsula.gpkg   (from 01_download.py; one row per pid)
Output: docs/data/geology.geojson             (EPSG:4326; pid, GLG, level1_class, level1_colour, level2_label)

Steps
1. coverage_clean: geo2bg's neighbouring polygons share edges geometrically but not vertex-for-vertex,
   so they are not a valid coverage and simplifying them separately would open gaps. GEOS CoverageCleaner
   snaps/nodes shared edges (snap 1e-6 deg ~ 0.1 m; slivers < 1e-4 deg wide merged). Area change is
   negligible (checked below).
2. coverage_simplify: topology-preserving simplification of each polygon; shared edges are simplified
   once, so neighbours stay gap- and overlap-free. Every pid is kept.
3. Coordinates rounded to PRECISION decimals (1e-4 deg ~ 11 m, far below TOLERANCE).
4. Bedrock/alluvium contacts at mountain fronts are moved to the foot of the slope in the terrain
   (scripts/contacts.py; regions and parameters there). Junctions stay fixed, so the result is still a
   coverage and every pid keeps one polygon. Adjusted polygons get contact_adjusted = 1. The unadjusted
   version is saved to data/interim/geology_web_unadjusted.gpkg. Skip with --no-adjust.

Checks (script stops if any fails): file < 8 MB; pid set == data/geology_polygons.csv; no empty or
invalid geometries; output is a valid coverage (no overlaps, shared edges identical); the union of all
polygons has no more holes than before (no gaps opened between neighbours).
"""
import json
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely

import contacts

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data" / "interim" / "geology_peninsula.gpkg"
POLY_TABLE = ROOT / "data" / "geology_polygons.csv"
OUT = ROOT / "docs" / "data" / "geology.geojson"
UNADJUSTED = ROOT / "data" / "interim" / "geology_web_unadjusted.gpkg"   # before/after maps

TOLERANCE = 0.004  # deg (~400 m); coverage_simplify tolerance
PRECISION = 4  # decimals kept in the GeoJSON
MAX_MB = 8.0
FIELDS = ["pid", "GLG", "level1_class", "level1_colour", "level2_label"]
FLAG = "contact_adjusted"   # set (1) only on polygons whose mountain-front contact was moved
EQUAL_AREA = 6933


def round_coords(geoms: np.ndarray, decimals: int) -> np.ndarray:
    # Deterministic per-vertex rounding: identical shared vertices stay identical.
    out = shapely.transform(geoms, lambda xy: np.round(xy, decimals))
    bad = ~shapely.is_valid(out)
    if bad.any():  # rare self-touch after rounding; make_valid keeps the polygon
        out[bad] = shapely.make_valid(out[bad], method="structure", keep_collapsed=False)
    return out


def area_km2(geoms) -> np.ndarray:
    return gpd.GeoSeries(geoms, crs=4326).to_crs(EQUAL_AREA).area.to_numpy() / 1e6


def main() -> None:
    gdf = gpd.read_file(SRC)
    assert gdf.crs.to_epsg() == 4326, gdf.crs
    geoms = gdf.geometry.to_numpy()
    n_in = shapely.get_num_coordinates(geoms).sum()
    print(f"Input: {len(gdf)} polygons, {n_in:,} vertices; valid coverage: {shapely.coverage_is_valid(geoms)}")

    cleaned = shapely.coverage_clean(geoms, gap_width=1e-4, snapping_distance=1e-6)
    a0, a1 = area_km2(geoms), area_km2(cleaned)
    print(f"Cleaned: valid coverage {shapely.coverage_is_valid(cleaned)}; "
          f"max per-polygon area change {np.abs(a1 - a0).max():.4f} km2")

    simple = shapely.coverage_simplify(cleaned, TOLERANCE, simplify_boundary=True)
    simple = round_coords(simple, PRECISION)

    # 4. DEM-guided adjustment of bedrock/alluvium contacts at mountain fronts (scripts/contacts.py)
    gpd.GeoDataFrame(gdf[FIELDS], geometry=simple, crs=4326).to_file(UNADJUSTED, driver="GPKG")
    a_before = area_km2(simple)
    if "--no-adjust" in sys.argv:
        adjusted = np.zeros(len(simple), bool)
        print("Contact adjustment skipped (--no-adjust)")
    else:
        print("Adjusting bedrock/alluvium contacts to the foot of slope (z10 Terrarium):")
        simple, adjusted, _ = contacts.adjust(simple, gdf["level1_class"], gdf["level2_label"].fillna(""))
        d = area_km2(simple) - a_before
        print(f"  polygons changed: {int(adjusted.sum())}; area moved between polygons: "
              f"{np.abs(d).sum() / 2:,.0f} km2; total area change {d.sum():+.2f} km2")

    # --- checks -------------------------------------------------------------------------------
    assert not shapely.is_empty(simple).any(), "empty geometry after simplification"
    assert shapely.is_valid(simple).all(), "invalid geometry after simplification"
    assert set(shapely.get_type_id(simple)) <= {3, 6}, "non-polygonal output"
    assert shapely.coverage_is_valid(simple), "output is not a valid coverage (overlap/edge mismatch)"
    # Gaps: compare holes in the union before and after (excluded H2O/U units are legitimate holes).
    u_in = shapely.coverage_union_all(cleaned)
    u_out = shapely.coverage_union_all(simple)
    holes = lambda u: sum(shapely.get_num_interior_rings(shapely.get_parts(u)))
    new_gap_area = area_km2([shapely.difference(u_in, u_out)])[0]
    print(f"Union holes before/after: {holes(u_in)}/{holes(u_out)}; "
          f"area in input not covered by output: {new_gap_area:.1f} km2 "
          f"(coastline/hole simplification, not inter-polygon gaps)")
    assert holes(u_out) <= holes(u_in), "simplification opened gaps between polygons"
    tot0, tot1 = a0.sum(), area_km2(simple).sum()
    print(f"Total area {tot0:,.0f} -> {tot1:,.0f} km2 ({100 * (tot1 - tot0) / tot0:+.3f} %)")

    ref = pd.read_csv(POLY_TABLE)
    assert len(ref) == len(gdf) and set(ref.pid) == set(gdf.pid), "pid set differs from geology_polygons.csv"

    # --- export -------------------------------------------------------------------------------
    props = gdf[FIELDS].astype(object).where(gdf[FIELDS].notna(), "").to_dict("records")
    for p, a in zip(props, adjusted):
        if a:
            p[FLAG] = 1
    feats = [
        {"type": "Feature", "properties": p, "geometry": shapely.geometry.mapping(g)}
        for p, g in zip(props, simple)
    ]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w") as f:
        json.dump({"type": "FeatureCollection", "features": feats}, f, separators=(",", ":"))

    mb = OUT.stat().st_size / 1e6
    n_out = shapely.get_num_coordinates(simple).sum()
    print(f"\nTolerance: {TOLERANCE} deg (~{TOLERANCE * 111:.2f} km); coordinates rounded to {PRECISION} decimals")
    print(f"Vertices: {n_in:,} -> {n_out:,}")
    print(f"Wrote {OUT.relative_to(ROOT)}: {len(feats)} features, {mb:.2f} MB")
    assert mb < MAX_MB, f"geology.geojson is {mb:.2f} MB (limit {MAX_MB} MB)"

    # Re-read check: what the viewer will get
    back = gpd.read_file(OUT)
    assert len(back) == len(ref) and set(back.pid) == set(ref.pid)
    assert back.is_valid.all() and not back.is_empty.any()
    assert [c for c in back.columns if c != FLAG] == FIELDS + ["geometry"], list(back.columns)
    print("Checks passed: pid set matches data/geology_polygons.csv; no empty/invalid geometries; "
          "valid coverage (no overlaps/gaps).")


if __name__ == "__main__":
    main()
