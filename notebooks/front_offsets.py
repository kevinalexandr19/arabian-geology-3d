"""Diagnostic: offset between mapped bedrock/surficial contacts and the slope break, at mountain fronts.

For each region, the shared edges between bedrock polygons and Neogene-Quaternary surficial polygons
are sampled every STEP_M. At each sample a slope profile is taken along the normal, from -L (bedrock
side) to +L (surficial side), from z10 Terrarium tiles (~140 m/px). Where the profile shows a clear
contrast (mean slope on the bedrock side minus the surficial side >= MIN_CONTRAST deg), the foot of the
slope is where the profile drops to the plain level + FOOT x contrast (alluvium meets rock at the foot). Offset > 0: the steep ground extends past
the mapped contact into the mapped alluvium; offset < 0: the mapped bedrock covers flat ground.

Outputs a table per region and notebooks/front_offsets.png. Tiles cached in data/interim/terrarium/.
"""

import math
import warnings
from pathlib import Path

import geopandas as gpd
import matplotlib
import numpy as np
import pandas as pd
import requests
import shapely
from rasterio.errors import NotGeoreferencedWarning
from rasterio.io import MemoryFile
from shapely.geometry import box

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

warnings.filterwarnings("ignore", category=NotGeoreferencedWarning)
ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data/interim/terrarium"
OUT = Path(__file__).resolve().parent
URL = "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"
Z, TILE = 10, 256
HALF = 20037508.342789244
SURFICIAL = "Neogene-Quaternary surficial deposits"
STEP_M, L_M, DS_M = 500, 8000, 250
MIN_CONTRAST = 5.0  # deg
FOOT = 0.25  # foot of slope = plain level + 25% of the contrast

REGIONS = {
    "Hajar front (Oman)": (56.0, 22.4, 59.0, 24.6),
    "Asir / Tihamah": (41.0, 16.5, 43.5, 20.5),
    "Yemen highlands": (43.0, 13.0, 45.5, 16.5),
    "Dhofar": (53.0, 16.8, 55.5, 17.8),
    "Musandam": (55.8, 25.4, 56.6, 26.4),
}


def merc(lon, lat):
    return HALF * lon / 180, HALF * math.log(math.tan(math.pi / 4 + math.radians(lat) / 2)) / math.pi


def get_tile(x, y):
    p = CACHE / f"{Z}_{x}_{y}.png"
    if not p.exists():
        r = requests.get(URL.format(z=Z, x=x, y=y), timeout=60)
        r.raise_for_status()
        p.write_bytes(r.content)
    with MemoryFile(p.read_bytes()) as m, m.open() as s:
        v = s.read([1, 2, 3]).astype(np.float32)
    return v[0] * 256 + v[1] + v[2] / 256 - 32768


def mosaic(b):
    n, res = 2 ** Z, 2 * HALF / (TILE * 2 ** Z)
    tx = lambda lon: int((lon + 180) / 360 * n)  # noqa: E731
    ty = lambda lat: int((1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n)  # noqa: E731
    x0, x1, y0, y1 = tx(b[0]), tx(b[2]), ty(b[3]), ty(b[1])
    dem = np.vstack([np.hstack([get_tile(x, y) for x in range(x0, x1 + 1)]) for y in range(y0, y1 + 1)])
    return dem, (-HALF + x0 * TILE * res, HALF - y0 * TILE * res, res)


def main():
    CACHE.mkdir(parents=True, exist_ok=True)
    geo = gpd.read_file(ROOT / "docs/data/geology.geojson")
    rows, examples = [], {}
    for name, b in REGIONS.items():
        dem, (ox, oy, res) = mosaic(b)
        k = math.cos(math.radians((b[1] + b[3]) / 2))      # mercator metres -> ground metres
        gy, gx = np.gradient(dem, res * k)
        slope = np.degrees(np.arctan(np.hypot(gx, gy)))
        g = geo[geo.intersects(box(*b))].to_crs(3857)
        bed = shapely.union_all(g[g.level1_class != SURFICIAL].geometry.buffer(0))
        sur = shapely.union_all(g[g.level1_class == SURFICIAL].geometry.buffer(0))
        contact = shapely.line_merge(shapely.intersection(bed.boundary, sur.boundary))
        contact = shapely.intersection(contact, box(*merc(b[0], b[1]), *merc(b[2], b[3])).buffer(-L_M / k))
        offs = np.arange(-L_M, L_M + 1, DS_M)
        for line in getattr(contact, "geoms", [contact]):
            if line.geom_type != "LineString" or line.length * k < 2 * STEP_M:
                continue
            for d in np.arange(STEP_M / k, line.length, STEP_M / k):
                p, q = line.interpolate(d - 50 / k), line.interpolate(d + 50 / k)
                tx_, ty_ = q.x - p.x, q.y - p.y
                nrm = math.hypot(tx_, ty_)
                if nrm == 0:
                    continue
                nx, ny = -ty_ / nrm, tx_ / nrm
                c = line.interpolate(d)
                # orient the normal from bedrock (-) to surficial (+)
                if not sur.contains(shapely.Point(c.x + nx * 300 / k, c.y + ny * 300 / k)):
                    nx, ny = -nx, -ny
                xs = c.x + nx * offs / k
                ys = c.y + ny * offs / k
                cols = ((xs - ox) / res).astype(int)
                rws = ((oy - ys) / res).astype(int)
                if cols.min() < 0 or rws.min() < 0 or cols.max() >= dem.shape[1] or rws.max() >= dem.shape[0]:
                    continue
                prof = slope[rws, cols]
                prof = np.convolve(prof, np.ones(3) / 3, mode="same")
                hi = prof[offs <= -3000].mean()
                lo = prof[offs >= 3000].mean()
                if hi - lo < MIN_CONTRAST:
                    continue
                mid = lo + FOOT * (hi - lo)
                # foot of the slope: crossing below `mid` going from the bedrock side to the surficial side
                above = prof > mid
                idx = np.where(above[:-1] & ~above[1:])[0]
                if not len(idx):
                    continue
                j = idx[np.argmin(abs(offs[idx]))]
                rows.append(dict(region=name, offset_km=offs[j] / 1000, contrast=hi - lo))
                if name not in examples or (hi - lo) > examples[name][2]:
                    examples[name] = (offs / 1000, prof, hi - lo)
        print(f"{name}: {sum(r['region'] == name for r in rows)} profiles with a clear front", flush=True)

    d = pd.DataFrame(rows)
    t = d.groupby("region").offset_km.agg(
        profiles="size", median="median",
        abs_median=lambda s: s.abs().median(),
        abs_p75=lambda s: s.abs().quantile(.75),
        within_1km=lambda s: (s.abs() <= 1).mean(),
        over_3km=lambda s: (s.abs() > 3).mean(),
    ).round(2)
    print("\nOffset of the slope break from the mapped contact (km; + = steep ground extends into mapped alluvium)")
    print(t.to_string())
    d.to_csv(OUT / "front_offsets.csv", index=False)

    fig, ax = plt.subplots(1, 2, figsize=(12, 4.2))
    for name in REGIONS:
        s = d[d.region == name].offset_km
        if len(s):
            ax[0].hist(s, bins=np.arange(-8, 8.25, 0.5), histtype="step", lw=1.5, label=f"{name} (n={len(s)})")
    ax[0].axvline(0, color="k", lw=.8)
    ax[0].set_xlabel("slope break − mapped contact (km)  [+ = mountain extends into mapped alluvium]")
    ax[0].set_ylabel("profiles"); ax[0].legend(fontsize=8)
    name = "Hajar front (Oman)"
    if name in examples:
        o, p, c = examples[name]
        ax[1].plot(o, p); ax[1].axvline(0, color="k", lw=.8)
        ax[1].set_xlabel("distance across mapped contact (km; − bedrock, + alluvium)")
        ax[1].set_ylabel("slope (°)"); ax[1].set_title(f"example profile, {name}")
    fig.tight_layout()
    fig.savefig(OUT / "front_offsets.png", dpi=110)
    print("wrote notebooks/front_offsets.png, notebooks/front_offsets.csv")


if __name__ == "__main__":
    main()
