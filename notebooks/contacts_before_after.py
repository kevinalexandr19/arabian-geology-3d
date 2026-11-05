"""Before/after maps of the DEM-guided contact adjustment (scripts/contacts.py), one set per area.

Before: data/interim/geology_web_unadjusted.gpkg (written by 02_geology.py)
After:  docs/data/geology.geojson
For each area: an overview and two close-ups (the 0.5 deg windows with the most change), each with
three panels on z10 hillshade: Before | After | Change (bedrock -> alluvium red, alluvium -> bedrock
blue; old contact dashed orange, new contact black).
Writes notebooks/contacts/<area>_{overview,zoom1,zoom2}.png and prints the area changed per area.
"""
import math
import sys
from pathlib import Path

import geopandas as gpd
import matplotlib
import numpy as np
import shapely

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import contacts as C  # noqa: E402

OUT = Path(__file__).resolve().parent / "contacts"
AREAS = {
    "hajar": ("Hajar Mountains", (56.0, 22.2, 59.9, 24.6)),
    "musandam": ("Musandam and northern Oman mountains", (55.5, 24.2, 56.6, 26.5)),
    "asir": ("Asir escarpment and Tihamah", (40.5, 16.3, 43.6, 21.5)),
    "yemen": ("Yemen highlands", (43.0, 12.6, 46.5, 16.6)),
    "dhofar": ("Dhofar", (52.5, 16.6, 55.6, 18.0)),
}
ZOOM_DEG = 0.5


def hillshade(grid, bbox, px_deg):
    """Hillshade resampled to a regular lon/lat grid (so it lines up with the polygons exactly)."""
    lons = np.arange(bbox[0], bbox[2], px_deg)
    lats = np.arange(bbox[3], bbox[1], -px_deg)
    LON, LAT = np.meshgrid(lons, lats)
    x = C.HALF * LON / 180
    y = C.HALF * np.log(np.tan(np.pi / 4 + np.radians(LAT) / 2)) / np.pi
    c = np.clip(((x - grid.ox) / grid.res).astype(int), 0, grid.dem.shape[1] - 1)
    r = np.clip(((grid.oy - y) / grid.res).astype(int), 0, grid.dem.shape[0] - 1)
    k = math.cos(math.radians((bbox[1] + bbox[3]) / 2))
    gy, gx = np.gradient(grid.dem, grid.res * k)
    gx, gy = gx * 1.5, gy * 1.5
    az, alt = np.radians(315), np.radians(45)
    slope = np.arctan(np.hypot(gx, gy))
    aspect = np.arctan2(-gx, gy)
    hs = np.sin(alt) * np.cos(slope) + np.cos(alt) * np.sin(slope) * np.cos(az - aspect)
    return np.clip(hs, 0, 1)[r, c]


def bedrock_union(g, box):
    sub = g[g.intersects(box) & (g.level1_class != C.SURFICIAL)]
    return shapely.intersection(shapely.union_all(sub.geometry.buffer(0).to_numpy()), box)


def panel(ax, hs, bbox, g, title, lines=None):
    ax.imshow(hs, cmap="gray", extent=(bbox[0], bbox[2], bbox[1], bbox[3]), vmin=0, vmax=1, interpolation="bilinear")
    box = shapely.box(*bbox)
    sub = g[g.intersects(box)]
    if len(sub):
        sub.plot(ax=ax, color=sub.level1_colour, alpha=.5, linewidth=0)
        sub.boundary.plot(ax=ax, color="#333", linewidth=.35)
    if lines is not None:
        for geom, style in lines:
            gpd.GeoSeries([geom]).plot(ax=ax, **style)
    ax.set_xlim(bbox[0], bbox[2]); ax.set_ylim(bbox[1], bbox[3])
    ax.set_aspect(1 / math.cos(math.radians((bbox[1] + bbox[3]) / 2)))
    ax.set_title(title, fontsize=11)
    ax.tick_params(labelsize=7)


def figure(name, title, bbox, before, after, grid, moved_before, moved_after):
    span = max(bbox[2] - bbox[0], bbox[3] - bbox[1])
    px = span / 1400
    hs = hillshade(grid, bbox, px)
    box = shapely.box(*bbox)
    b0, b1 = bedrock_union(before, box), bedrock_union(after, box)
    lost, gained = shapely.difference(b0, b1), shapely.difference(b1, b0)
    km2 = lambda geom: gpd.GeoSeries([geom], crs=4326).to_crs(6933).area.iloc[0] / 1e6  # noqa: E731
    # Show only contacts next to real changes (re-simplified but unmoved edges differ by < 150 m)
    near = shapely.intersection(shapely.union(lost, gained).buffer(0.003), box)
    old = shapely.intersection(moved_before, near)
    new = shapely.intersection(moved_after, near)
    fig, axs = plt.subplots(1, 3, figsize=(18, 6.6))
    panel(axs[0], hs, bbox, before, "Before (geo2bg, simplified)")
    panel(axs[1], hs, bbox, after, "After (contacts at foot of slope)")
    axs[2].imshow(hs, cmap="gray", extent=(bbox[0], bbox[2], bbox[1], bbox[3]), vmin=0, vmax=1)
    for geom, col in ((lost, "#d7301f"), (gained, "#2166ac")):
        if not geom.is_empty:
            gpd.GeoSeries([geom]).plot(ax=axs[2], color=col, alpha=.6, linewidth=0)
    if not old.is_empty:
        gpd.GeoSeries([old]).plot(ax=axs[2], color="#ff8c00", linewidth=1.1, linestyle="--")
    if not new.is_empty:
        gpd.GeoSeries([new]).plot(ax=axs[2], color="black", linewidth=1.1)
    axs[2].set_xlim(bbox[0], bbox[2]); axs[2].set_ylim(bbox[1], bbox[3])
    axs[2].set_aspect(1 / math.cos(math.radians((bbox[1] + bbox[3]) / 2)))
    axs[2].set_title(f"Change: {km2(lost):,.0f} km² bedrock→alluvium, {km2(gained):,.0f} km² alluvium→bedrock",
                     fontsize=11)
    axs[2].tick_params(labelsize=7)
    axs[2].set_xlabel("Geodetic longitude [degree]"); axs[2].set_ylabel("Geodetic latitude [degree]")
    axs[2].legend(handles=[Patch(color="#d7301f", alpha=.6, label="bedrock → alluvium"),
                           Patch(color="#2166ac", alpha=.6, label="alluvium → bedrock"),
                           Line2D([], [], color="#ff8c00", ls="--", label="contact before"),
                           Line2D([], [], color="black", label="contact after")],
                  loc="lower left", fontsize=8, framealpha=.9)
    fig.suptitle(title, fontsize=14)
    fig.tight_layout()
    OUT.mkdir(exist_ok=True)
    fig.savefig(OUT / f"{name}.png", dpi=100)
    plt.close(fig)
    return km2(lost), km2(gained)


def main():
    before = gpd.read_file(ROOT / "data/interim/geology_web_unadjusted.gpkg")
    after = gpd.read_file(ROOT / "docs/data/geology.geojson")
    assert list(before.pid) == list(after.pid)
    changed = ~before.geometry.geom_equals_exact(after.geometry, 1e-9)
    # Moved contacts = boundary pieces that differ between before and after
    bnd0 = shapely.union_all(before[changed].boundary.to_numpy())
    bnd1 = shapely.union_all(after[changed].boundary.to_numpy())
    moved_before, moved_after = shapely.difference(bnd0, bnd1), shapely.difference(bnd1, bnd0)
    print(f"polygons changed: {int(changed.sum())}")
    for key, (title, bbox) in AREAS.items():
        grid = C.SlopeGrid(bbox)
        lost, gained = figure(f"{key}_overview", f"{title}: overview", bbox, before, after, grid,
                              moved_before, moved_after)
        print(f"{title}: {lost:,.0f} km2 bedrock->alluvium, {gained:,.0f} km2 alluvium->bedrock", flush=True)
        # Close-ups: 0.5 deg windows with the most change
        diff = shapely.symmetric_difference(bedrock_union(before, shapely.box(*bbox)),
                                            bedrock_union(after, shapely.box(*bbox)))
        cands = []
        for x in np.arange(bbox[0], bbox[2] - ZOOM_DEG / 2, ZOOM_DEG / 2):
            for y in np.arange(bbox[1], bbox[3] - ZOOM_DEG / 2, ZOOM_DEG / 2):
                w = shapely.box(x, y, x + ZOOM_DEG, y + ZOOM_DEG)
                cands.append((shapely.intersection(diff, w).area, (x, y, x + ZOOM_DEG, y + ZOOM_DEG)))
        cands.sort(reverse=True)
        picked = []
        for a, w in cands:
            if a == 0 or len(picked) == 2:
                break
            if all(not shapely.intersects(shapely.box(*w), shapely.box(*p)) for p in picked):
                picked.append(w)
        for n, w in enumerate(picked, 1):
            figure(f"{key}_zoom{n}", f"{title}: close-up {n} ({w[0]:.2f}–{w[2]:.2f}°E, {w[1]:.2f}–{w[3]:.2f}°N)",
                   w, before, after, grid, moved_before, moved_after)
    print(f"wrote {OUT.relative_to(ROOT)}/*.png")


if __name__ == "__main__":
    main()
