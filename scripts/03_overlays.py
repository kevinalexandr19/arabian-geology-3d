"""M2: cities and roads (already clipped to the peninsula mask by 01_download.py) -> GeoJSON for the viewer.

Cities: every Natural Earth 10m populated place inside the mask, joined to scripts/cities.csv by the NE
`NAME`. cities.csv gives the name in regional English usage (e.g. Madinah, Jazan, Sohar, Sana'a), a curated
Arabic name (NE's NAME_AR has errors) and an include flag (only Hawalli, part of Kuwait City, is excluded).
The script stops if a place has no row in cities.csv, so new NE places can't slip through unnamed.
Fields: name, name_ar, scalerank (NE label priority, 0 = most important), capital (1 = national capital).

Roads: OpenStreetMap highway=motorway|trunk|primary (from 01_download.py, clipped to the peninsula mask).
Natural Earth 10m roads were replaced because they are generalized to 1:10M and miss or misclassify trunk
routes (NE `type` "Unknown" includes trunk roads). Ways are merged per (class, ref); ways without a ref are
merged per (class, name). Each merged feature takes the most frequent (by length) English and Arabic name.
Fields: class (motorway/trunk/primary), ref, name_en (name:en, else name if Latin), name_ar (name:ar, else
name if Arabic). Light simplification (SIMPLIFY_DEG), dropping parts < MIN_PART_KM and 4-decimal coordinates keep the file small.
A check lists NE 10m roads (from the M1 interim layer) that have no OSM counterpart within MATCH_KM.
Licence: roads.geojson is derived from OpenStreetMap, (c) OpenStreetMap contributors, ODbL 1.0.

Outputs: docs/data/cities.geojson, docs/data/roads.geojson (EPSG:4326)
"""
import json
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely

ROOT = Path(__file__).resolve().parents[1]
INTERIM = ROOT / "data" / "interim"
CITY_TABLE = ROOT / "scripts" / "cities.csv"
OUT = ROOT / "docs" / "data"

ROAD_CLASSES = ["primary", "trunk", "motorway"]  # draw order: primary first, motorway on top
SIMPLIFY_DEG = 0.001  # ~100 m
MIN_PART_KM = 0.5     # drop roundabouts, interchange fragments and clip slivers (~1% of length)
MATCH_KM = 5           # NE 1:10M lines can sit a few km off the true road
NE_MAJOR_TYPES = ["Major Highway", "Road"]
NE_MAJOR_MAX_SCALERANK = 7
METRIC = 32638         # UTM 38N, distances only
PRECISION = 4  # decimals (~11 m)


def write_geojson(gdf: gpd.GeoDataFrame, path: Path) -> None:
    geoms = shapely.transform(gdf.geometry.to_numpy(), lambda xy: np.round(xy, PRECISION))
    props = gdf.drop(columns="geometry").to_dict("records")
    feats = [{"type": "Feature", "properties": p, "geometry": shapely.geometry.mapping(g)}
             for p, g in zip(props, geoms)]
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"type": "FeatureCollection", "features": feats}, f, separators=(",", ":"), ensure_ascii=False)
    print(f"Wrote {path.relative_to(ROOT)}: {len(feats)} features, {path.stat().st_size / 1e3:.0f} kB")


def cities() -> gpd.GeoDataFrame:
    places = gpd.read_file(INTERIM / "populated_places_peninsula.gpkg")
    table = pd.read_csv(CITY_TABLE, dtype={"notes": str})
    missing = set(places.NAME) - set(table.ne_name)
    assert not missing, f"places missing from {CITY_TABLE.name}: {sorted(missing)}"
    unused = set(table.ne_name) - set(places.NAME)
    assert not unused, f"rows in {CITY_TABLE.name} with no NE place: {sorted(unused)}"
    m = places.merge(table, left_on="NAME", right_on="ne_name", validate="one_to_one")
    m = m[m.include == 1]
    out = gpd.GeoDataFrame({
        "name": m["name"],
        "name_ar": m["name_ar"],
        "scalerank": m.SCALERANK.astype(int),
        "capital": (m.ADM0CAP == 1).astype(int),
        "geometry": m.geometry,
    }, crs=places.crs).sort_values(["scalerank", "name"])
    renamed = m[m.NAME != m["name"]]
    print(f"Cities: {len(out)} of {len(places)} NE places (excluded: "
          f"{', '.join(table.loc[table.include == 0, 'ne_name'])}); {len(renamed)} renamed to regional usage:")
    print("  " + "; ".join(f"{a} -> {b}" for a, b in zip(renamed.NAME, renamed["name"])))
    assert 40 <= len(out) <= 80, len(out)
    return out


def _arabic(t: str) -> bool:
    return any("\u0600" <= ch <= "\u06ff" for ch in t)


def _top(values: pd.Series, weights: pd.Series) -> str:
    w = weights[values != ""].groupby(values[values != ""]).sum()
    return w.idxmax() if len(w) else ""


def roads() -> gpd.GeoDataFrame:
    r = gpd.read_file(INTERIM / "osm_roads_peninsula.gpkg").explode(index_parts=False)
    r = r.fillna("")
    r["name_en"] = r.name_en.where(r.name_en != "", r["name"].where(~r["name"].map(_arabic), ""))
    r["name_ar"] = r.name_ar.where(r.name_ar != "", r["name"].where(r["name"].map(_arabic), ""))
    r["km"] = r.to_crs(METRIC).length / 1e3
    r["key"] = np.where(r.ref != "", "ref:" + r.ref, "name:" + r.name_en.where(r.name_en != "", r.name_ar))
    rows = []
    for (cls, key), g in r.groupby(["highway", "key"], sort=False):
        merged = shapely.line_merge(shapely.MultiLineString(list(g.geometry)))
        rows.append({"class": cls, "ref": g.ref.iloc[0], "name_en": _top(g.name_en, g.km),
                     "name_ar": _top(g.name_ar, g.km), "geometry": merged.simplify(SIMPLIFY_DEG)})
    out = gpd.GeoDataFrame(rows, crs=r.crs).explode(index_parts=False)
    out = out[out.to_crs(METRIC).length >= MIN_PART_KM * 1e3]
    out = out.dissolve(["class", "ref", "name_en", "name_ar"], as_index=False, sort=False)
    out["order"] = out["class"].map(ROAD_CLASSES.index)
    out = out.sort_values(["order", "ref", "name_en"]).drop(columns="order")
    km = out.to_crs(METRIC).length / 1e3
    print(f"Roads: {len(r)} OSM ways -> {len(out)} features (merged per class+ref / class+name), {km.sum():,.0f} km")
    print(pd.DataFrame({"class": out["class"], "has_ref": out.ref != "", "km": km})
          .groupby(["class", "has_ref"]).agg(features=("km", "size"), km=("km", "sum")).round(0).to_string())
    return out


def compare_ne(osm: gpd.GeoDataFrame, places: gpd.GeoDataFrame) -> None:
    """List NE 10m roads with no OSM motorway/trunk/primary within MATCH_KM (sampled every 2 km)."""
    ne = gpd.read_file(INTERIM / "roads_peninsula.gpkg").to_crs(METRIC).explode(index_parts=False)
    ne = ne.reset_index(drop=True)
    tree = shapely.STRtree(osm.to_crs(METRIC).geometry.to_numpy())
    city = places.to_crs(METRIC)
    ne_major = ne["type"].str.strip().isin(NE_MAJOR_TYPES) | (ne.scalerank <= NE_MAJOR_MAX_SCALERANK)
    rows = []
    for i, line in enumerate(ne.geometry):
        d = np.arange(0, line.length + 1, 2000)
        pts = shapely.line_interpolate_point(line, d)
        _, dist = tree.query_nearest(pts, return_distance=True, all_matches=False)
        miss = dist > MATCH_KM * 1e3
        if miss.mean() < 0.5:
            continue
        a, b = pts[miss][0], pts[miss][-1]
        ends = [city.iloc[city.distance(p).argmin()]["name"] for p in (a, b)]
        lon, lat = gpd.GeoSeries([a, b], crs=METRIC).to_crs(4326).iloc[0].coords[0]
        rows.append({"NE": "major" if ne_major[i] else "secondary", "type": ne.at[i, "type"].strip(),
                     "scalerank": int(ne.scalerank[i]), "km": round(line.length / 1e3),
                     "uncovered": f"{miss.mean():.0%}", "near": " - ".join(dict.fromkeys(ends)),
                     "start": f"{lon:.2f}E {lat:.2f}N"})
    t = pd.DataFrame(rows).sort_values(["NE", "km"], ascending=[True, False])
    tot = ne.length / 1e3
    print(f"\nNE 10m roads vs OSM: {len(t)} of {len(ne)} NE lines have >=50% of their length more than "
          f"{MATCH_KM} km from any OSM motorway/trunk/primary ({t.km.sum():,.0f} of {tot.sum():,.0f} km).")
    print(t.to_string(index=False))


def main() -> None:
    c, r = cities(), roads()
    assert c.crs.to_epsg() == 4326 and r.crs.to_epsg() == 4326
    write_geojson(c, OUT / "cities.geojson")
    write_geojson(r, OUT / "roads.geojson")
    compare_ne(r, c)


if __name__ == "__main__":
    main()
