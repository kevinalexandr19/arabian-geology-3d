"""M2 preview: docs/data/*.geojson rendered with matplotlib -> notebooks/m2_preview.png.

Left: whole peninsula (L1 fill colours, major roads, cities). Right: zoom on the Shield / Harrat Rahat
near Medina with polygon edges drawn, to check visually for gaps or overlaps after simplification.
"""
from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt
from matplotlib.patches import Patch, Rectangle

ROOT = Path(__file__).resolve().parents[1]
D = ROOT / "docs" / "data"
OUT = ROOT / "notebooks" / "m2_preview.png"
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

roads.plot(ax=ax, color=roads["type"].map({"Major Highway": "#333333", "Road": "#777777"}),
           linewidth=roads["type"].map({"Major Highway": 0.9, "Road": 0.5}))
roads.plot(ax=az, color="#333333", linewidth=1.0)
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
classes = geo.drop_duplicates("level1_class")[["level1_class", "level1_colour"]]
order = ["Precambrian basement (Arabian Shield)", "Paleozoic", "Triassic", "Jurassic", "Cretaceous",
         "Tertiary sedimentary", "Cenozoic volcanics", "Cenozoic eolian sand and gravel"]
cmap = dict(zip(classes.level1_class, classes.level1_colour))
ax.legend(handles=[Patch(fc=cmap[k], ec="none", label=k) for k in order], loc="upper right", fontsize=8,
          framealpha=0.9)
ax.set_title(f"geology.geojson ({len(geo)} polygons), {len(roads)} major roads, {len(cities)} cities")
az.set_title("Zoom: Shield and Harrat Rahat near Medina (polygon edges in black)")
fig.text(0.01, 0.01, "Geology: USGS OFR 97-470B (geo2bg). Cities, roads: Natural Earth. EPSG:4326.",
         fontsize=8)
fig.tight_layout()
fig.savefig(OUT, dpi=110)
print(f"Wrote {OUT.relative_to(ROOT)} ({OUT.stat().st_size / 1e3:.0f} kB)")
