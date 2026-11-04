"""M2: cities and roads (already clipped to the peninsula mask by 01_download.py) -> GeoJSON for the viewer.

Cities: every Natural Earth 10m populated place inside the mask, joined to scripts/cities.csv by the NE
`NAME`. cities.csv gives the name in regional English usage (e.g. Madinah, Jazan, Sohar, Sana'a), a curated
Arabic name (NE's NAME_AR has errors) and an include flag (only Hawalli, part of Kuwait City, is excluded).
The script stops if a place has no row in cities.csv, so new NE places can't slip through unnamed.
Fields: name, name_ar, scalerank (NE label priority, 0 = most important), capital (1 = national capital).

Roads: ALL Natural Earth 10m roads inside the mask. NE's `type` field is unreliable here: "Unknown" includes
trunk routes (e.g. Hail-Buraydah, Najran-Sharurah, Al Kharj-Haradh, Mukalla-Salalah, Muscat-Sur,
Sohar-Ibri), some at scalerank 8-9, so no attribute filter is safe. A `class` field is added for styling:
  major     = type "Major Highway" or "Road", or scalerank <= 7
  secondary = the rest (NE "Unknown"/"Track", scalerank 8-10)
Fields: class, type, scalerank.

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

MAJOR_TYPES = ["Major Highway", "Road"]
MAJOR_MAX_SCALERANK = 7
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


def roads() -> gpd.GeoDataFrame:
    r = gpd.read_file(INTERIM / "roads_peninsula.gpkg")
    rtype = r["type"].str.strip()
    major = rtype.isin(MAJOR_TYPES) | (r.scalerank <= MAJOR_MAX_SCALERANK)
    out = gpd.GeoDataFrame({
        "class": np.where(major, "major", "secondary"),
        "type": rtype,
        "scalerank": r.scalerank.astype(int),
        "geometry": r.geometry,
    }, crs=r.crs).sort_values("class", ascending=False)  # secondary first, major drawn on top
    km = out.to_crs(6933).length / 1e3
    print(f"Roads: all {len(out)} NE features in the mask, {km.sum():,.0f} km")
    print(pd.DataFrame({"class": out["class"], "type": out["type"], "km": km})
          .groupby(["class", "type"]).agg(features=("km", "size"), km=("km", "sum")).round(0).to_string())
    return out


def main() -> None:
    c, r = cities(), roads()
    assert c.crs.to_epsg() == 4326 and r.crs.to_epsg() == 4326
    write_geojson(c, OUT / "cities.geojson")
    write_geojson(r, OUT / "roads.geojson")


if __name__ == "__main__":
    main()
