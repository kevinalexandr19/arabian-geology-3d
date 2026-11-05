"""M4: elevation statistics per geology class from AWS Terrarium tiles.

Downloads the z7 Terrarium tiles covering docs/data/geology.geojson (cached in
data/interim/terrarium/), mosaics them on their native EPSG:3857 grid,
rasterizes the geology polygons onto the same grid and computes per-pixel
statistics (min, p10, median, p90, max, pixel count, negative-pixel count)
per Level 1 class and per Level 2 label. Writes docs/data/elev_stats.json.

Pixel weighting: every ~1.2 km pixel counts once (no per-polygon averaging).
Note that EPSG:3857 pixels shrink in ground area towards the north
(cos(lat): 0.97 at 13°N, 0.85 at 32°N); this is ignored.
"""

import json
import math
import sys
import warnings
from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio
import requests
from rasterio.features import rasterize
from rasterio.io import MemoryFile
from rasterio.errors import NotGeoreferencedWarning
from rasterio.transform import from_origin

warnings.filterwarnings("ignore", category=NotGeoreferencedWarning)

ROOT = Path(__file__).resolve().parents[1]
GEOLOGY = ROOT / "docs/data/geology.geojson"
UNITS = ROOT / "docs/data/units.json"
CACHE = ROOT / "data/interim/terrarium"
OUT = ROOT / "docs/data/elev_stats.json"

Z = 7
TILE = 256
URL = "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"
HALF = 20037508.342789244  # EPSG:3857 half-extent, m


def lonlat_to_tile(lon, lat, z):
    n = 2**z
    x = int((lon + 180) / 360 * n)
    y = int((1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n)
    return x, y


def get_tile(x, y):
    path = CACHE / f"{Z}_{x}_{y}.png"
    if not path.exists():
        r = requests.get(URL.format(z=Z, x=x, y=y), timeout=60)
        r.raise_for_status()
        path.write_bytes(r.content)
    with MemoryFile(path.read_bytes()) as mem, mem.open() as src:
        rgb = src.read([1, 2, 3]).astype(np.float64)
    return rgb[0] * 256 + rgb[1] + rgb[2] / 256 - 32768


def stats(v):
    if v.size == 0:
        return None
    p = np.percentile(v, [0, 10, 50, 90, 100])
    return {
        "min": round(float(p[0])), "p10": round(float(p[1])), "median": round(float(p[2])),
        "p90": round(float(p[3])), "max": round(float(p[4])),
        "n_px": int(v.size), "n_neg": int((v < 0).sum()),
    }


def main():
    CACHE.mkdir(parents=True, exist_ok=True)
    geo = gpd.read_file(GEOLOGY)
    lon0, lat0, lon1, lat1 = geo.total_bounds
    x0, y0 = lonlat_to_tile(lon0, lat1, Z)  # NW
    x1, y1 = lonlat_to_tile(lon1, lat0, Z)  # SE
    nx, ny = x1 - x0 + 1, y1 - y0 + 1
    print(f"z{Z} tiles x {x0}-{x1}, y {y0}-{y1} ({nx * ny} tiles)")

    dem = np.empty((ny * TILE, nx * TILE), dtype=np.float32)
    for j in range(ny):
        for i in range(nx):
            dem[j * TILE:(j + 1) * TILE, i * TILE:(i + 1) * TILE] = get_tile(x0 + i, y0 + j)

    res = 2 * HALF / (TILE * 2**Z)
    transform = from_origin(-HALF + x0 * TILE * res, HALF - y0 * TILE * res, res, res)
    print(f"mosaic {dem.shape[1]} x {dem.shape[0]} px, {res:.0f} m/px (EPSG:3857)")

    geo = geo.to_crs(3857)
    classes = [c["name"] for c in json.loads(UNITS.read_text())["classes"]]
    unknown = set(geo.level1_class) - set(classes)
    if unknown:
        sys.exit(f"classes not in units.json: {unknown}")
    labels = sorted(l for l in geo.level2_label.fillna("").unique() if l)

    def burn(col, keys):
        idx = {k: i + 1 for i, k in enumerate(keys)}
        shapes = ((g, idx[k]) for g, k in zip(geo.geometry, geo[col].fillna("")) if k in idx)
        return rasterize(shapes, out_shape=dem.shape, transform=transform, fill=0, dtype="uint16")

    r1 = burn("level1_class", classes)
    r2 = burn("level2_label", labels)

    out = {
        "source": "AWS Terrain Tiles (Terrarium), z7, EPSG:3857 grid, ~1.2 km/px",
        "method": "per-pixel statistics of all pixels whose centre falls inside the polygons",
        "level1": {}, "level2": {},
    }
    for i, c in enumerate(classes, 1):
        out["level1"][c] = stats(dem[r1 == i])
    for i, l in enumerate(labels, 1):
        out["level2"][l] = stats(dem[r2 == i])
    OUT.write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n")
    print(f"wrote {OUT.relative_to(ROOT)}\n")

    def table(title, d):
        print(f"{title:<40} {'min':>6} {'p10':>6} {'med':>6} {'p90':>6} {'max':>6} {'pixels':>8} {'neg':>6}")
        for k, s in d.items():
            print(f"{k:<40} {s['min']:>6} {s['p10']:>6} {s['median']:>6} {s['p90']:>6} {s['max']:>6} {s['n_px']:>8} {s['n_neg']:>6}")
        print()

    table("Level 1 class", out["level1"])
    table("Level 2 label", out["level2"])

    # Sanity checks.
    L1, L2 = out["level1"], out["level2"]
    pg = L1["Paleogene-Neogene sedimentary"]["median"]
    checks = [
        ("Precambrian median > Paleogene-Neogene median + 300 m",
         L1["Precambrian basement (Arabian Shield)"]["median"] > pg + 300),
        ("Cenozoic volcanics median > Paleogene-Neogene median + 300 m",
         L1["Cenozoic volcanics"]["median"] > pg + 300),
        ("Sabkha median within ±30 m of 0", abs(L2["Sabkha"]["median"]) <= 30),
    ]
    for name, ok in checks:
        print(f"[{'PASS' if ok else 'FAIL'}] {name}")
    sab = L2["Sabkha"]
    print(f"      Sabkha p10 = {sab['p10']} m, median = {sab['median']} m. Coastal sabkhas sit at 0-10 m; inland\n"
          "      sabkhas (Umm as Samim, landward Sabkha Matti, Rub' al Khali interdune flats, Al Jafr playa)\n"
          "      raise the median, so a failure here is expected and is not a processing error.")


if __name__ == "__main__":
    main()
