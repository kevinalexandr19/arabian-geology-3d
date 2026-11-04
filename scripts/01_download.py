"""M1: fetch Natural Earth places + roads, clip all inputs to the study bbox, print a summary.

geo2bg (USGS OFR 97-470B) is already in the repo at data/raw/geology/ and is not downloaded.
Outputs: data/raw/naturalearth/*.zip (gitignored), data/interim/*.gpkg (clipped, gitignored).
"""
from pathlib import Path

import geopandas as gpd
import requests
from shapely.geometry import box

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
NE_DIR = RAW / "naturalearth"
INTERIM = ROOT / "data" / "interim"
GEO_SHP = RAW / "geology" / "geo2bg.shp"

BBOX = (34.0, 12.0, 60.0, 33.0)  # lon_min, lat_min, lon_max, lat_max (EPSG:4326)

NE_URLS = {
    "populated_places": "https://naciscdn.org/naturalearth/10m/cultural/ne_10m_populated_places.zip",
    "roads": "https://naciscdn.org/naturalearth/10m/cultural/ne_10m_roads.zip",
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


def clip(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    if gdf.crs is None or gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs(4326)
    return gpd.clip(gdf, box(*BBOX))


def summary(name: str, raw: gpd.GeoDataFrame, clipped: gpd.GeoDataFrame) -> None:
    print(f"\n=== {name} ===")
    print(f"CRS:      {raw.crs.to_string() if raw.crs else None}")
    print(f"Features: {len(raw)} total -> {len(clipped)} in bbox {BBOX}")
    print(f"Geometry: {sorted(clipped.geom_type.unique())}")
    print(f"Fields:   {[c for c in raw.columns if c != 'geometry']}")


def main() -> None:
    print("Downloading Natural Earth layers")
    zips = {k: download(u, NE_DIR / Path(u).name) for k, u in NE_URLS.items()}

    INTERIM.mkdir(parents=True, exist_ok=True)

    # Geology
    geo = gpd.read_file(GEO_SHP)
    geo_c = clip(geo)
    summary("geo2bg (USGS OFR 97-470B)", geo, geo_c)
    geo_c = geo_c.assign(area_km2=geo_c.to_crs(6933).area / 1e6)  # equal-area for stats only
    units = (geo_c.groupby("GLG")
             .agg(polygons=("GLG", "size"), area_km2=("area_km2", "sum"))
             .sort_values("area_km2", ascending=False))
    units["area_km2"] = units["area_km2"].round(0).astype(int)
    print("\nUnique GLG units in bbox (polygon count, area km2):")
    print(units.to_string())
    geo_c.drop(columns="area_km2").to_file(INTERIM / "geology_clip.gpkg", driver="GPKG")

    # Natural Earth
    for key, z in zips.items():
        gdf = gpd.read_file(f"zip://{z}")
        gdf_c = clip(gdf)
        summary(f"Natural Earth 10m {key}", gdf, gdf_c)
        if key == "populated_places":
            print("SCALERANK counts in bbox:", gdf_c["SCALERANK"].value_counts().sort_index().to_dict())
        else:
            print("type counts in bbox:", gdf_c["type"].value_counts().to_dict())
            print("scalerank counts in bbox:", gdf_c["scalerank"].value_counts().sort_index().to_dict())
        gdf_c.to_file(INTERIM / f"{key}_clip.gpkg", driver="GPKG")

    print(f"\nClipped layers written to {INTERIM.relative_to(ROOT)}/")


if __name__ == "__main__":
    main()
