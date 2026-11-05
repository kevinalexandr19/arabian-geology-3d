"""Diagnostic: how far is the geo2bg geology offset from the terrain, and is the offset systematic?

Bedrock (every Level 1 class except the surficial one) is rough and steep; Neogene-Quaternary surficial
deposits are flat. In each 1 x 1 deg window the bedrock indicator is cross-correlated (FFT) with the
terrain slope from z8 Terrarium tiles (~0.55 km/px), for shifts up to +/-MAX_SHIFT px. The best shift
is the displacement that would move the geology onto the relief. Windows with too little contrast or a
weak correlation peak are skipped.

Outputs: notebooks/alignment_vectors.png (shift vectors), notebooks/alignment_windows.csv, and a summary.
Tiles are cached in data/interim/terrarium/.
"""

import math
import sys
import warnings
from pathlib import Path

import geopandas as gpd
import matplotlib
import numpy as np
import pandas as pd
import requests
from rasterio.errors import NotGeoreferencedWarning
from rasterio.features import rasterize
from rasterio.io import MemoryFile
from rasterio.transform import from_origin

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

warnings.filterwarnings("ignore", category=NotGeoreferencedWarning)
ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data/interim/terrarium"
OUT = Path(__file__).resolve().parent
Z, TILE = 8, 256
HALF = 20037508.342789244
URL = "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"
SURFICIAL = "Neogene-Quaternary surficial deposits"
MAX_SHIFT = 12          # px (~6.5 km)
MIN_FRAC, MAX_FRAC = 0.15, 0.85   # bedrock fraction needed in a window
MIN_PEAK = 0.05         # correlation gain of the best shift over zero shift, to count as a clear peak


def tile(x, y):
    p = CACHE / f"{Z}_{x}_{y}.png"
    if not p.exists():
        r = requests.get(URL.format(z=Z, x=x, y=y), timeout=60)
        r.raise_for_status()
        p.write_bytes(r.content)
    with MemoryFile(p.read_bytes()) as m, m.open() as s:
        v = s.read([1, 2, 3]).astype(np.float32)
    return v[0] * 256 + v[1] + v[2] / 256 - 32768


def lonlat_to_tile(lon, lat):
    n = 2 ** Z
    return int((lon + 180) / 360 * n), int((1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n)


def ncc_shift(b, s, m):
    """Best (dy, dx) shift of bedrock window b (h x w) against slope s ((h+2m) x (w+2m)), by FFT."""
    h, w = b.shape
    bz = (b - b.mean()) / (b.std() + 1e-9)
    big = np.zeros_like(s)
    big[m:m + h, m:m + w] = bz
    sz = (s - s.mean()) / (s.std() + 1e-9)
    c = np.fft.irfft2(np.fft.rfft2(sz) * np.conj(np.fft.rfft2(big)), s=s.shape)
    c = np.roll(c, (m, m), axis=(0, 1))[: 2 * m + 1, : 2 * m + 1] / (h * w)  # c[m+dy, m+dx]
    k = np.unravel_index(np.argmax(c), c.shape)
    return k[0] - m, k[1] - m, float(c[k]), float(c[m, m])


def main():
    CACHE.mkdir(parents=True, exist_ok=True)
    geo = gpd.read_file(ROOT / "docs/data/geology.geojson")
    lon0, lat0, lon1, lat1 = geo.total_bounds
    x0, y0 = lonlat_to_tile(lon0, lat1)
    x1, y1 = lonlat_to_tile(lon1, lat0)
    print(f"z{Z}: {(x1 - x0 + 1) * (y1 - y0 + 1)} tiles", flush=True)
    dem = np.vstack([np.hstack([tile(x, y) for x in range(x0, x1 + 1)]) for y in range(y0, y1 + 1)])
    res = 2 * HALF / (TILE * 2 ** Z)
    tr = from_origin(-HALF + x0 * TILE * res, HALF - y0 * TILE * res, res, res)

    g3 = geo.to_crs(3857)
    bed = rasterize(((gm, 1) for gm, c in zip(g3.geometry, g3.level1_class) if c != SURFICIAL),
                    out_shape=dem.shape, transform=tr, fill=0, dtype="uint8").astype(np.float32)
    land = rasterize(((gm, 1) for gm in g3.geometry), out_shape=dem.shape, transform=tr,
                     fill=0, dtype="uint8").astype(bool)
    gy, gx = np.gradient(dem, res)
    slope = np.hypot(gx, gy)
    # Smooth 3x3 to reduce DEM noise
    slope = sum(np.roll(np.roll(slope, i, 0), j, 1) for i in (-1, 0, 1) for j in (-1, 0, 1)) / 9

    rows = []
    for la in np.arange(math.floor(lat0), math.ceil(lat1)):
        for lo in np.arange(math.floor(lon0), math.ceil(lon1)):
            # window in pixels
            def to_px(lon, lat):
                X = HALF * lon / 180
                Y = HALF * math.log(math.tan(math.pi / 4 + math.radians(lat) / 2)) / math.pi
                return int((X - tr.c) / res), int((tr.f - Y) / res)
            c0, r0 = to_px(lo, la + 1)
            c1, r1 = to_px(lo + 1, la)
            m = MAX_SHIFT
            if r0 - m < 0 or c0 - m < 0 or r1 + m > dem.shape[0] or c1 + m > dem.shape[1]:
                continue
            lw = land[r0:r1, c0:c1]
            if lw.mean() < 0.9:    # coastal windows: the sea would dominate the slope
                continue
            b = bed[r0:r1, c0:c1]
            f = b.mean()
            if not MIN_FRAC <= f <= MAX_FRAC:
                continue
            s = slope[r0 - m:r1 + m, c0 - m:c1 + m]
            dy, dx, best, zero = ncc_shift(b, s, m)
            km = res * math.cos(math.radians(la + 0.5)) / 1000
            rows.append(dict(lon=lo + 0.5, lat=la + 0.5, bedrock_frac=round(f, 2),
                             dx_km=round(dx * km, 2), dy_km=round(-dy * km, 2),  # +dy_km = north
                             shift_km=round(math.hypot(dx, dy) * km, 2),
                             r_zero=round(zero, 3), r_best=round(best, 3), gain=round(best - zero, 3),
                             at_edge=abs(dx) == m or abs(dy) == m))
    w = pd.DataFrame(rows)
    w.to_csv(OUT / "alignment_windows.csv", index=False)
    clear = w[(w.gain >= MIN_PEAK) & ~w.at_edge]
    print(f"windows analysed: {len(w)}; with a clear peak: {len(clear)}; best shift at search edge: {int(w.at_edge.sum())}")
    print(f"r at zero shift (median): {w.r_zero.median():.3f}; at best shift: {w.r_best.median():.3f}")
    print("shift needed, km (all windows): median {:.1f}, p75 {:.1f}, p90 {:.1f}".format(
        w.shift_km.median(), w.shift_km.quantile(.75), w.shift_km.quantile(.9)))
    if len(clear):
        print("shift needed, km (clear windows): median {:.1f}, p75 {:.1f}, p90 {:.1f}".format(
            clear.shift_km.median(), clear.shift_km.quantile(.75), clear.shift_km.quantile(.9)))
        print(f"mean vector of clear windows: dx {clear.dx_km.mean():+.2f} km E, dy {clear.dy_km.mean():+.2f} km N")
        # Coherence: how similar is each clear vector to the mean of its clear neighbours (within 1.5 deg)?
        sims = []
        for _, r in clear.iterrows():
            nb = clear[(abs(clear.lon - r.lon) <= 1.5) & (abs(clear.lat - r.lat) <= 1.5) &
                       ((clear.lon != r.lon) | (clear.lat != r.lat))]
            if len(nb) >= 2 and r.shift_km > 0:
                v, u = np.array([r.dx_km, r.dy_km]), np.array([nb.dx_km.mean(), nb.dy_km.mean()])
                if np.linalg.norm(u) > 0:
                    sims.append(float(v @ u / (np.linalg.norm(v) * np.linalg.norm(u))))
        if sims:
            print(f"neighbour coherence (cosine, 1 = same direction): median {np.median(sims):.2f} over {len(sims)} windows")
    print(w.sort_values("gain", ascending=False).head(15).to_string(index=False))

    fig, ax = plt.subplots(figsize=(10, 8.5))
    geo.plot(ax=ax, color=geo.level1_colour, linewidth=0, alpha=.55)
    weak = w.drop(clear.index)
    ax.scatter(weak.lon, weak.lat, s=8, c="grey", label="no clear peak")
    q = ax.quiver(clear.lon, clear.lat, clear.dx_km, clear.dy_km, clear.shift_km, cmap="viridis",
                  angles="xy", scale_units="xy", scale=8, width=.004)
    plt.colorbar(q, ax=ax, shrink=.6, label="shift that best aligns geology to relief (km)")
    ax.set_title("geo2bg vs terrain: best-fit shift of the geology per 1° window (arrow length: 1° = 8 km)")
    ax.set_xlim(34, 60); ax.set_ylim(12, 32.5); ax.set_aspect(1 / math.cos(math.radians(22)))
    ax.legend(loc="lower left")
    fig.savefig(OUT / "alignment_vectors.png", dpi=110, bbox_inches="tight")
    print("wrote notebooks/alignment_vectors.png, notebooks/alignment_windows.csv")


if __name__ == "__main__":
    sys.exit(main())
