"""M2 preview: docs/data/*.geojson rendered with matplotlib -> notebooks/m2_preview.png.

Left: whole peninsula (L1 fill colours, OSM roads by class, cities). Right: zoom on the Shield / Harrat Rahat
near Madinah with polygon edges drawn, to check visually for gaps or overlaps after simplification.
"""
from pathlib import Path

import geopandas as gpd
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.patches import Patch, Rectangle

ROOT = Path(__file__).resolve().parents[1]
D = ROOT / "docs" / "data"
OUT = ROOT / "notebooks" / "m2_preview.png"
ROAD_STYLE = (("primary", "#777777", 0.4), ("trunk", "#222222", 0.8), ("motorway", "#b2182b", 1.0))
ZOOM = (38.8, 22.6, 40.6, 24.8)  # lon_min, lat_min, lon_max, lat_max

geo = gpd.read_file(D / "geology.geojson")
roads = gpd.read_file(D / "roads.geojson")
cities = gpd.read_file(D / "cities.geojson")

fig, (ax, az) = plt.subplots(1, 2, figsize=(18, 10), gridspec_kw={"width_ratios": [1.6, 1]})
for a in (ax, az):
    geo.plot(ax=a, color=geo.level1_colour, linewidth=0)
    a.set_facecolor("#cfe3ef")
    a.set_aspect("equal")
geo.boundary.plot(ax=az, color="k", linewidth=0.25)

for a, scale in ((ax, 1.0), (az, 1.6)):
    for cls, colour, lw in ROAD_STYLE:
        roads[roads["class"] == cls].plot(ax=a, color=colour, linewidth=lw * scale)
for a, size in ((ax, 5.5), (az, 9)):
    cities.plot(ax=a, color="k", markersize=cities["capital"].map({1: 22, 0: 8}), zorder=3)
    for _, c in cities.iterrows():
        x, y = c.geometry.x, c.geometry.y
        if a is az and not (ZOOM[0] < x < ZOOM[2] and ZOOM[1] < y < ZOOM[3]):
            continue
        a.annotate(c["name"], (x, y), xytext=(3, 2), textcoords="offset points", fontsize=size,
                   fontweight="bold" if c.scalerank <= 4 else "normal", zorder=4)

ax.set_xlim(34.3, 60.0); ax.set_ylim(12.4, 32.3)
az.set_xlim(ZOOM[0], ZOOM[2]); az.set_ylim(ZOOM[1], ZOOM[3])
ax.add_patch(Rectangle(ZOOM[:2], ZOOM[2] - ZOOM[0], ZOOM[3] - ZOOM[1], fill=False, ec="k", lw=1.2))
classes = (pd.read_csv(ROOT / "scripts" / "geology_classes.csv")
           .query("level1_class != 'EXCLUDE'").drop_duplicates("level1_class"))
handles = [Patch(fc=c, ec="none", label=k) for k, c in zip(classes.level1_class, classes.level1_colour)]
handles += [plt.Line2D([], [], color=c, lw=lw * 1.5, label=f"OSM {k}") for k, c, lw in ROAD_STYLE[::-1]]
ax.legend(handles=handles, loc="upper right", fontsize=8, framealpha=0.9)
ax.set_title(f"geology.geojson ({len(geo)} polygons), {len(roads)} road features, {len(cities)} cities")
az.set_title("Zoom: Shield and Harrat Rahat near Madinah (polygon edges in black)")
fig.text(0.01, 0.01, "Geology: USGS OFR 97-470B (geo2bg). Cities: Natural Earth. "
         "Roads: (c) OpenStreetMap contributors, ODbL. EPSG:4326.",
         fontsize=8)
fig.tight_layout()
fig.savefig(OUT, dpi=110)
print(f"Wrote {OUT.relative_to(ROOT)} ({OUT.stat().st_size / 1e3:.0f} kB)")
