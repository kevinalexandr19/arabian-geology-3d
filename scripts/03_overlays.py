"""M2: select cities and major roads (already clipped to the peninsula mask by 01_download.py) and export
GeoJSON for the viewer.

Cities: Natural Earth 10m populated_places with SCALERANK <= 8 (drops the 6 least important of 74 places
inside the mask). Fields: name, pop (POP_MAX), scalerank, capital (1 = national capital), for label
size/priority in the viewer.

Roads: Natural Earth 10m roads with type "Major Highway" or "Road". Drops type "Unknown" (mostly
scalerank 8-10 minor links) and "Track". Fields: type, scalerank.

Outputs: docs/data/cities.geojson, docs/data/roads.geojson (EPSG:4326)
"""
import json
from pathlib import Path

import geopandas as gpd
import numpy as np
import shapely

ROOT = Path(__file__).resolve().parents[1]
INTERIM = ROOT / "data" / "interim"
OUT = ROOT / "docs" / "data"

CITY_MAX_SCALERANK = 8
ROAD_TYPES = ["Major Highway", "Road"]
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


def main() -> None:
    places = gpd.read_file(INTERIM / "populated_places_peninsula.gpkg")
    cities = places[places.SCALERANK <= CITY_MAX_SCALERANK].copy()
    cities = gpd.GeoDataFrame({
        "name": cities.NAME,
        "pop": cities.POP_MAX.astype(int),
        "scalerank": cities.SCALERANK.astype(int),
        "capital": (cities.ADM0CAP == 1).astype(int),
        "geometry": cities.geometry,
    }, crs=places.crs).sort_values(["scalerank", "pop"], ascending=[True, False])
    print(f"Cities: SCALERANK <= {CITY_MAX_SCALERANK} -> {len(cities)} of {len(places)}")
    assert 40 <= len(cities) <= 80, len(cities)

    roads = gpd.read_file(INTERIM / "roads_peninsula.gpkg")
    major = roads[roads["type"].isin(ROAD_TYPES)]
    major = gpd.GeoDataFrame({
        "type": major["type"],
        "scalerank": major.scalerank.astype(int),
        "geometry": major.geometry,
    }, crs=roads.crs)
    km = major.to_crs(6933).length.sum() / 1e3
    print(f"Roads: type in {ROAD_TYPES} -> {len(major)} of {len(roads)} features, {km:,.0f} km")
    print(major["type"].value_counts().to_string())

    assert cities.crs.to_epsg() == 4326 and major.crs.to_epsg() == 4326
    write_geojson(cities, OUT / "cities.geojson")
    write_geojson(major, OUT / "roads.geojson")


if __name__ == "__main__":
    main()
