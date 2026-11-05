"""DEM-guided adjustment of bedrock / alluvium contacts at mountain fronts (used by 02_geology.py).

geo2bg contacts come from a 1963 1:2,000,000 map. At mountain fronts the mapped bedrock/alluvium
contact is typically 1-2 km from the foot of the slope in the SRTM-based terrain (see
notebooks/front_offsets.py). This module moves those contacts, and only those, onto the foot of the
slope:

1. Edge network: the coverage's shared boundaries are split into edges between junctions. An edge is
   selected when one side is bedrock (any Level 1 class except the surficial one) and the other is
   alluvium/gravel/sabkha (surficial class without the "Eolian sand" label: dunes have their own slopes),
   and it lies in one of REGIONS.
2. Measurement: every STEP_KM along the edge, a slope profile (z10 AWS Terrarium tiles, ~140 m/px) is
   taken along the normal, +/-L_KM. Where the profile shows a mountain front (bedrock-side mean slope
   >= MIN_HI deg, alluvium-side mean <= MAX_LO deg, contrast >= MIN_CONTRAST deg), the foot of the slope
   is where the profile falls to the plain level + FOOT x contrast (crossing nearest the mapped contact).
   It is only used if there is a real break there: mean slope >= MIN_HI within 0.3-1.5 km on the bedrock
   side of it and <= MAX_LO within 0.3-1.5 km on the alluvium side (so flat plateaux are not moved).
3. Smoothing: offsets are filled between measurements, filtered along the edge (running median, then
   running mean) and capped at +/-MAX_KM. They fade to zero away from measured stretches (GAP_KM +
   TAPER_KM), so only the parts of an edge that are a mountain front move, and over TAPER_KM at both ends,
   so junctions do not move and neighbouring edges are untouched.
4. Safety: a moved edge must be simple, must not cross any other edge and must not sweep over any other
   edge (that would swallow a small polygon). Otherwise the move is scaled down (x0.5, x0.25) or dropped.
5. Rebuild: polygons touching a moved edge are rebuilt from their edges, so shared edges stay identical
   and every pid keeps one polygon. 02_geology.py then re-checks the whole coverage.

Contacts between two bedrock units (e.g. Jurassic/Cretaceous) and harrat edges are not touched: slope
does not define them.
"""
from __future__ import annotations

import math
import warnings
from pathlib import Path

import numpy as np
import requests
import shapely
from rasterio.errors import NotGeoreferencedWarning
from rasterio.io import MemoryFile

warnings.filterwarnings("ignore", category=NotGeoreferencedWarning)

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data" / "interim" / "terrarium"
URL = "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"
HALF = 20037508.342789244

SURFICIAL = "Neogene-Quaternary surficial deposits"
NOT_ADJUSTED_LABELS = {"Eolian sand"}

# Areas where contacts are adjusted (lon_min, lat_min, lon_max, lat_max)
REGIONS = {
    "Hajar and Musandam": (55.5, 22.2, 59.9, 26.5),
    "Asir and Tihamah": (40.5, 16.3, 43.6, 21.5),
    "Yemen highlands": (43.0, 12.6, 46.5, 16.6),
    "Dhofar": (52.5, 16.6, 55.6, 18.0),
}

Z, TILE = 10, 256
STEP_KM = 0.3        # vertex spacing for measurement
L_KM = 8.0           # profile half-length
DS_KM = 0.2          # profile sample step
SIDE_KM = 2.5        # inner limit of the windows used for the bedrock / plain slope levels
MIN_HI, MAX_LO, MIN_CONTRAST = 8.0, 6.0, 5.0   # deg
FOOT = 0.25
BREAK_KM = (0.3, 1.5)  # the new contact needs >= MIN_HI deg within this range inside, <= MAX_LO outside
MIN_MEASURED = 5     # measured vertices needed to move (part of) an edge
GAP_KM = 0.5         # full move within this distance of a measured vertex, fading to 0 over TAPER_KM
TANGENT_K = 3        # tangent / normal from vertices i-3 .. i+3
MEDIAN_WIN, MEAN_WIN = 9, 7   # vertices (~2.7 km, ~2.1 km)
MAX_KM = 5.0
TAPER_KM = 1.5
MIN_EDGE_KM = 1.0
SIMPLIFY_DEG = 0.0015   # moved edges are re-simplified (~150 m) to keep the GeoJSON small
DECIMALS = 4


# ---------------------------------------------------------------------------------------------
# Terrain
class SlopeGrid:
    """Slope (degrees) on the z10 Web-Mercator grid covering bbox."""

    def __init__(self, bbox):
        n = 2 ** Z
        tx = lambda lon: int((lon + 180) / 360 * n)  # noqa: E731
        ty = lambda lat: int((1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n)  # noqa: E731
        pad = 0.1
        x0, x1 = tx(bbox[0] - pad), tx(bbox[2] + pad)
        y0, y1 = ty(bbox[3] + pad), ty(bbox[1] - pad)
        dem = np.vstack([np.hstack([_tile(x, y) for x in range(x0, x1 + 1)]) for y in range(y0, y1 + 1)])
        self.res = 2 * HALF / (TILE * n)
        self.ox, self.oy = -HALF + x0 * TILE * self.res, HALF - y0 * TILE * self.res
        k = math.cos(math.radians((bbox[1] + bbox[3]) / 2))
        gy, gx = np.gradient(dem, self.res * k)
        self.slope = np.degrees(np.arctan(np.hypot(gx, gy))).astype(np.float32)
        self.dem = dem

    def sample(self, lon, lat):
        x = HALF * lon / 180
        y = HALF * np.log(np.tan(np.pi / 4 + np.radians(lat) / 2)) / np.pi
        c = ((x - self.ox) / self.res).astype(int)
        r = ((self.oy - y) / self.res).astype(int)
        ok = (c >= 0) & (r >= 0) & (c < self.slope.shape[1]) & (r < self.slope.shape[0])
        out = np.full(lon.shape, np.nan, dtype=np.float32)
        out[ok] = self.slope[r[ok], c[ok]]
        return out


def _tile(x, y):
    CACHE.mkdir(parents=True, exist_ok=True)
    p = CACHE / f"{Z}_{x}_{y}.png"
    if not p.exists():
        r = requests.get(URL.format(z=Z, x=x, y=y), timeout=60)
        r.raise_for_status()
        p.write_bytes(r.content)
    with MemoryFile(p.read_bytes()) as m, m.open() as s:
        v = s.read([1, 2, 3]).astype(np.float32)
    return v[0] * 256 + v[1] + v[2] / 256 - 32768


# ---------------------------------------------------------------------------------------------
# Edge network
def edge_network(geoms):
    """Edges between junctions and, for each, the indices of the polygons on either side."""
    lines = shapely.union_all(shapely.boundary(geoms))
    edges = list(shapely.get_parts(shapely.line_merge(lines)))
    tree = shapely.STRtree(geoms)
    bnd = shapely.boundary(geoms)
    adj = []
    for e in edges:
        c = np.asarray(e.coords)
        p = shapely.Point((c[0] + c[1]) / 2)
        cand = tree.query(p.buffer(1e-6))
        adj.append([int(i) for i in cand if shapely.distance(bnd[i], p) < 1e-9])
    return edges, adj


def _running(a, win, fn, closed):
    """Running filter of odd width `win`; wraps around for closed rings, edge-padded otherwise."""
    h = win // 2
    if len(a) <= win:
        return np.full_like(a, fn(a))
    if closed:   # a[0] == a[-1] (same vertex)
        ap = np.concatenate([a[-h - 1:-1], a, a[1:h + 1]])
    else:
        ap = np.concatenate([np.full(h, a[0]), a, np.full(h, a[-1])])
    return fn(np.lib.stride_tricks.sliding_window_view(ap, win), axis=1)


def measure_edge(edge, sur_left, grid):
    """Smoothed offsets (km, + = towards the alluvium) and normals for a densified edge; None to skip."""
    d = shapely.segmentize(edge, STEP_KM / 111.0)
    xy = np.asarray(d.coords)
    closed = d.is_closed
    lat0 = xy[:, 1].mean()
    kx, ky = 111.32 * math.cos(math.radians(lat0)), 110.57
    pk = xy * [kx, ky]
    # Tangent over +/-TANGENT_K vertices (~1.8 km): smooth normals, no loops on tight bends
    k = TANGENT_K
    if closed:
        ring = pk[:-1]
        t = np.roll(ring, -k, 0) - np.roll(ring, k, 0)
        t = np.vstack([t, t[:1]])
    else:
        idx = np.arange(len(pk))
        t = pk[np.minimum(idx + k, len(pk) - 1)] - pk[np.maximum(idx - k, 0)]
    t /= np.linalg.norm(t, axis=1, keepdims=True) + 1e-12
    n = np.stack([-t[:, 1], t[:, 0]], 1)          # left normal
    if not sur_left:
        n = -n                                     # now points from bedrock to alluvium
    o = np.arange(-L_KM, L_KM + DS_KM / 2, DS_KM)
    P = pk[:, None, :] + n[:, None, :] * o[None, :, None]
    lon, lat = P[..., 0] / kx, P[..., 1] / ky
    prof = grid.sample(lon, lat)
    prof = (np.roll(prof, 1, 1) + prof + np.roll(prof, -1, 1)) / 3
    with np.errstate(invalid="ignore"), warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        hi = np.nanmean(prof[:, o <= -SIDE_KM], 1)
        lo = np.nanmean(prof[:, o >= SIDE_KM], 1)
        ok = (hi >= MIN_HI) & (lo <= MAX_LO) & (hi - lo >= MIN_CONTRAST)
        level = lo + FOOT * (hi - lo)
        above = prof > level[:, None]
    cross = above[:, :-1] & ~above[:, 1:]
    off = np.full(len(xy), np.nan)
    pos = (o[:-1] + o[1:]) / 2
    for i in np.where(ok)[0]:
        k = np.where(cross[i])[0]
        if not len(k):
            continue
        f = pos[k[np.argmin(np.abs(pos[k]))]]
        # There must be a real break right at the new contact: steep just inside, flat just outside.
        inside = prof[i, (o >= f - BREAK_KM[1]) & (o <= f - BREAK_KM[0])]
        outside = prof[i, (o >= f + BREAK_KM[0]) & (o <= f + BREAK_KM[1])]
        if np.nanmean(inside) >= MIN_HI and np.nanmean(outside) <= MAX_LO:
            off[i] = f
    good = ~np.isnan(off)
    if good.sum() < MIN_MEASURED:
        return None
    idx = np.arange(len(off))
    s = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(pk, axis=0), axis=1))])
    # Only move where measured: weight fades from 1 to 0 between GAP_KM and GAP_KM + TAPER_KM
    # away from the nearest measured vertex.
    dist = np.abs(s[:, None] - s[good][None, :]).min(1)
    weight = np.clip(1 - (dist - GAP_KM) / TAPER_KM, 0, 1)
    off = np.interp(idx, idx[good], off[good])
    off = _running(off, MEDIAN_WIN, np.median, closed)
    off = _running(off, MEAN_WIN, np.mean, closed)
    off = np.clip(off, -MAX_KM, MAX_KM)
    weight = _running(weight, MEAN_WIN, np.mean, closed)
    off *= weight
    if not closed:
        off *= np.clip(np.minimum(s, s[-1] - s) / TAPER_KM, 0, 1)
    return dict(xy=xy, n=n, off=off, kx=kx, ky=ky, closed=closed, measured=float(good.mean()))


def moved_line(m, scale):
    xy = m["xy"] + m["n"] * (m["off"] * scale)[:, None] / [m["kx"], m["ky"]]
    if m["closed"]:
        xy[-1] = xy[0]
    else:
        xy[0], xy[-1] = m["xy"][0], m["xy"][-1]
    line = shapely.simplify(shapely.LineString(xy), SIMPLIFY_DEG, preserve_topology=True)
    line = shapely.set_precision(line, 10 ** -DECIMALS, mode="pointwise")
    return shapely.remove_repeated_points(line)


def _endpoints(line):
    c = np.asarray(line.coords)
    return {tuple(np.round(c[0], DECIMALS)), tuple(np.round(c[-1], DECIMALS))}


def safe(new, old, i, cur, tree):
    if new.is_empty or not new.is_simple or new.length == 0:
        return False
    if shapely.equals(new, old):
        return False
    ends = _endpoints(old)
    swept = shapely.union_all(list(shapely.get_parts(shapely.polygonize([shapely.union(old, new)]))))
    zone = shapely.union(new, swept) if not swept.is_empty else new
    for j in tree.query(shapely.box(*zone.bounds).buffer(MAX_KM / 100)):
        if j == i:
            continue
        g = cur[j]
        inter = shapely.intersection(new, g)
        if not inter.is_empty:
            pts = [tuple(np.round(p.coords[0], DECIMALS)) for p in shapely.get_parts(inter)
                   if p.geom_type == "Point"]
            if len(pts) != len(shapely.get_parts(inter)) or not set(pts) <= ends:
                return False
        if not swept.is_empty and shapely.intersects(g, swept):
            # touching the swept area only at shared endpoints is fine
            rest = shapely.difference(shapely.intersection(g, swept), shapely.MultiPoint(list(ends)).buffer(1e-9))
            if not rest.is_empty and rest.length > 1e-9:
                return False
    return True


# ---------------------------------------------------------------------------------------------
def adjust(geoms, level1, level2, log=print):
    """Return (new_geoms, adjusted_mask, report rows). geoms: valid coverage, EPSG:4326, rounded."""
    geoms = np.asarray(geoms, dtype=object)
    level1, level2 = np.asarray(level1), np.asarray(level2)
    bedrock = level1 != SURFICIAL
    adjustable_sur = (level1 == SURFICIAL) & ~np.isin(level2, list(NOT_ADJUSTED_LABELS))

    edges, adj = edge_network(geoms)
    log(f"Edge network: {len(edges)} edges")
    cur = list(edges)
    tree = shapely.STRtree(edges)
    report, moved = [], set()
    for name, bbox in REGIONS.items():
        region = shapely.box(*bbox)
        grid = None
        n_sel = n_moved = n_scaled = 0
        shifts = []
        for i, e in enumerate(edges):
            a = adj[i]
            if len(a) != 2 or i in moved:
                continue
            b_side = [k for k in a if bedrock[k]]
            s_side = [k for k in a if adjustable_sur[k]]
            if len(b_side) != 1 or len(s_side) != 1:
                continue
            if not region.contains(shapely.centroid(e)):
                continue
            km = e.length * 111.0 * math.cos(math.radians(e.centroid.y))
            if km < MIN_EDGE_KM:
                continue
            n_sel += 1
            if grid is None:
                grid = SlopeGrid(bbox)
            # is the alluvium on the left of the edge direction?
            c = np.asarray(e.coords)
            mid = (c[0] + c[1]) / 2
            t = c[1] - c[0]
            left = shapely.Point(mid + np.array([-t[1], t[0]]) / (np.linalg.norm(t) + 1e-15) * 1e-6)
            sur_left = shapely.contains(geoms[s_side[0]], left) or not shapely.contains(geoms[b_side[0]], left)
            m = measure_edge(e, sur_left, grid)
            if m is None or np.abs(m["off"]).max() < 0.2:
                continue
            for scale in (1.0, 0.5, 0.25):
                new = moved_line(m, scale)
                if safe(new, e, i, cur, tree):
                    cur[i] = new
                    moved.add(i)
                    n_moved += 1
                    n_scaled += scale < 1
                    shifts.append(np.abs(m["off"] * scale))
                    break
        sh = np.concatenate(shifts) if shifts else np.array([0.0])
        report.append(dict(region=name, candidate_edges=n_sel, moved_edges=n_moved, scaled_down=n_scaled,
                           median_shift_km=round(float(np.median(sh)), 2),
                           p90_shift_km=round(float(np.quantile(sh, .9)), 2)))
        log(f"  {name}: {n_sel} bedrock/alluvium edges, {n_moved} moved ({n_scaled} scaled down); "
            f"vertex shift median {np.median(sh):.2f} km, p90 {np.quantile(sh, .9):.2f} km")

    # Rebuild polygons that touch a moved edge
    poly_edges = [[] for _ in geoms]
    for i, a in enumerate(adj):
        for k in a:
            poly_edges[k].append(i)
    touched = sorted({k for i in moved for k in adj[i]})
    out = geoms.copy()
    for k in touched:
        built = shapely.build_area(shapely.MultiLineString([cur[i] for i in poly_edges[k]]))
        parts = shapely.get_parts(built)
        assert len(parts) == 1, f"polygon {k} rebuilt into {len(parts)} parts"
        out[k] = parts[0]
    adjusted = np.zeros(len(geoms), bool)
    adjusted[touched] = True
    return out, adjusted, report
