"""Point and line layers for the viewer's Explore section and the plate overlay.

1. Holocene volcanoes: Smithsonian Global Volcanism Program, Volcanoes of the World (VOTW), via the GVP
   WFS service. Kept: volcanoes in Saudi Arabia and Yemen (incl. the Red Sea islands). Harrat Ash Shaam
   (Syria-Jordan-Saudi Arabia) is left out: its GVP point lies outside the peninsula. Fields: vnum, name
   (GVP name re-ordered, "Harrat Rahat" not "Rahat, Harrat"), type, landform, rock, elev_m, last_eruption
   (GVP year; negative = BCE; null = Holocene, date unknown), note (short context written here, optional).
   Citation: Global Volcanism Program, Volcanoes of the World, Smithsonian Institution (doi:10.5479/si.GVP.VOTW5).
2. Plate boundaries: Bird (2003) PB2002 model, "steps" file (GeoJSON by Hugo Ahlenius, Nordpil; ODC-BY 1.0).
   Steps within the map area are classified by STEPCLASS: spreading (OSR, CRB), transform (OTF, CTF) and
   convergent (SUB, OCB, CCB); consecutive steps of the same boundary and class are merged into lines
   and thinned to a vertex every ~5 km.
   Fields: cls, plates ("AR-AF"), name (plate names), v_mm (mean relative velocity, mm/yr).
3. Geoheritage sites and geoparks: curated in scripts/geoheritage.csv (coordinates approximate, ~1 km;
   see the `verify` column). Each site also gets the Level 1 class of the polygon it falls in.

Outputs: docs/data/volcanoes.geojson, docs/data/plates.geojson, docs/data/geoheritage.geojson
Downloads are cached in data/interim/places/.
"""
import csv
import json
from pathlib import Path

import requests
from shapely.geometry import Point, shape
from shapely.strtree import STRtree

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data" / "interim" / "places"
OUT = ROOT / "docs" / "data"
SITES = ROOT / "scripts" / "geoheritage.csv"

GVP_WFS = ("https://webservices.volcano.si.edu/geoserver/GVP-VOTW/ows?service=WFS&version=1.0.0"
           "&request=GetFeature&typeName=GVP-VOTW:Smithsonian_VOTW_Holocene_Volcanoes"
           "&outputFormat=application/json&bbox=34,12,60,32.5")
PB_STEPS = "https://raw.githubusercontent.com/fraxen/tectonicplates/master/GeoJSON/PB2002_steps.json"
PLATE_BBOX = (28.0, 5.0, 66.0, 38.0)  # lon/lat window of the plate overlay
THIN = 5  # keep every 5th vertex of the densified steps (~5 km), plus the end point
COUNTRIES = {"Saudi Arabia", "Yemen"}

STEP_CLASS = {"OSR": "spreading", "CRB": "spreading", "OTF": "transform", "CTF": "transform",
              "SUB": "convergent", "OCB": "convergent", "CCB": "convergent"}
PLATES = {"AR": "Arabia", "AF": "Africa (Nubia)", "SO": "Somalia", "IN": "India", "EU": "Eurasia",
          "AT": "Anatolia", "AS": "Aegean Sea"}

# Short context for the better-known volcanoes (shown in the viewer card, below the GVP facts).
VOLCANO_NOTES = {
    "Rahat, Harrat": "The AD 1256 fissure eruption sent a basalt flow to within about 8 km of Madinah; "
                     "the field covers some 20,000 km² of the Shield.",
    "Lunayyir, Harrat": "A 2009 dyke intrusion caused an earthquake swarm and ground cracking, and the "
                        "evacuation of Al Ays, without an eruption.",
    "Khaybar, Harrat": "Basaltic cones and flows with evolved trachyte–comendite domes (Jabal Abyad); "
                       "Jabal Qidr has some of the youngest flows.",
    "Tair, Jebel at": "Island volcano on the Red Sea axis; the 2007–2008 eruption was its first in over a century.",
    "Zubair Group": "Two new islands were built by Surtseyan eruptions in 2011–2012 and 2013, "
                    "on the axis of the southern Red Sea rift.",
    "Yar, Jabal": "Basaltic cones near the Saudi–Yemeni Red Sea coastal plain; last activity reported around 1810.",
    "Sawad, Harra Es-": "Lava field behind Aden; an eruption is reported for AD 1253.",
    "Arhab, Harra of": "Quaternary lava field north of Sana'a on the Yemen plateau.",
    "Dhamar, Harras of": "Lava fields and cones of the Yemen highlands south of Sana'a.",
    "Bir Borhut": "A small field of cones and a fuming well in eastern Yemen.",
}


def get(url, name):
    CACHE.mkdir(parents=True, exist_ok=True)
    f = CACHE / name
    if not f.exists():
        r = requests.get(url, timeout=300)
        r.raise_for_status()
        f.write_bytes(r.content)
    return json.loads(f.read_text())


def display_name(n):
    """'Rahat, Harrat' -> 'Harrat Rahat'; 'Tair, Jebel at' -> 'Jebel at Tair'."""
    if ", " in n:
        a, b = n.split(", ", 1)
        if b.endswith("-"):  # "Sawad, Harra Es-" -> "Harra es-Sawad"
            h, art = b[:-1].rsplit(" ", 1)
            return f"{h} {art.lower()}-{a}"
        return f"{b} {a}"
    return n


def volcanoes():
    gj = get(GVP_WFS, "gvp_votw.json")
    feats = []
    for f in gj["features"]:
        p = f["properties"]
        if p["Country"] not in COUNTRIES:
            continue
        lon, lat = f["geometry"]["coordinates"][:2]
        feats.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [round(lon, 4), round(lat, 4)]},
            "properties": {
                "vnum": p["Volcano_Number"], "name": display_name(p["Volcano_Name"]),
                "type": p["Primary_Volcano_Type"], "landform": p["Volcanic_Landform"],
                "rock": p["Major_Rock_Type"], "elev_m": p["Elevation"],
                "last_eruption": p["Last_Eruption_Year"], "evidence": p["Evidence_Category"],
                "note": VOLCANO_NOTES.get(p["Volcano_Name"], ""),
            },
        })
    # North to south, as listed in the panel.
    feats.sort(key=lambda f: -f["geometry"]["coordinates"][1])
    return feats


def plates():
    gj = get(PB_STEPS, "pb2002_steps.json")
    x0, y0, x1, y1 = PLATE_BBOX
    runs = []  # merged lines: consecutive steps of one boundary and class
    for f in gj["features"]:
        p = f["properties"]
        cls = STEP_CLASS.get(p["STEPCLASS"])
        c = f["geometry"]["coordinates"]
        if cls is None or not all(x0 <= x <= x1 and y0 <= y <= y1 for x, y in c):
            continue
        last = runs[-1] if runs else None
        # Each step is a densified line (vertices every ~1 km); chain steps that share an end point.
        if last and last["plates"] == p["PLATEBOUND"] and last["cls"] == cls and last["coords"][-1] == c[0]:
            last["coords"].extend(c[1:])
            last["v"].append(p["VELOCITYLE"])
        else:
            runs.append({"plates": p["PLATEBOUND"], "cls": cls, "coords": list(c), "v": [p["VELOCITYLE"]]})
    feats = []
    for r in runs:
        a, b = r["plates"].replace("/", "-").split("-")[:2]
        feats.append({
            "type": "Feature",
            "geometry": {"type": "LineString", "coordinates": [[round(x, 3), round(y, 3)] for x, y in
                                                               (r["coords"][::THIN] + r["coords"][-1:])]},
            "properties": {"cls": r["cls"], "plates": f"{a}-{b}",
                           "name": f"{PLATES.get(a, a)} – {PLATES.get(b, b)}",
                           "v_mm": round(sum(r["v"]) / len(r["v"]), 1)},
        })
    return feats


def sites():
    geo = json.loads((OUT / "geology.geojson").read_text())["features"]
    polys = [shape(f["geometry"]) for f in geo]
    tree = STRtree(polys)
    feats = []
    with SITES.open(newline="") as fh:
        for r in csv.DictReader(fh):
            lon, lat = float(r["lon"]), float(r["lat"])
            pt = Point(lon, lat)
            hit = [i for i in tree.query(pt) if polys[i].contains(pt)]
            l1 = geo[hit[0]]["properties"]["level1_class"] if hit else ""
            feats.append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [lon, lat]},
                "properties": {"id": r["id"], "name": r["name"], "kind": r["kind"], "description": r["description"],
                               "zoom": float(r["zoom"]), "pitch": float(r["pitch"]), "bearing": float(r["bearing"]),
                               "level1_class": l1},
            })
    return feats


def write(name, feats):
    path = OUT / name
    path.write_text(json.dumps({"type": "FeatureCollection", "features": feats}, ensure_ascii=False,
                               separators=(",", ":")))
    print(f"{name}: {len(feats)} features, {path.stat().st_size / 1024:.1f} KB")


if __name__ == "__main__":
    v = volcanoes()
    write("volcanoes.geojson", v)
    for f in v:
        p = f["properties"]
        print(f"  {p['name']:<28} last eruption {p['last_eruption']}  ({p['type']})")
    pl = plates()
    write("plates.geojson", pl)
    s = sites()
    write("geoheritage.geojson", s)
    for f in s:
        p = f["properties"]
        print(f"  {p['name']:<40} {p['kind']:<8} on: {p['level1_class'] or '(no geology polygon)'}")
