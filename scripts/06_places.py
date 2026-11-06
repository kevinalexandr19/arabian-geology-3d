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
   see the `verify` column). Each site also gets the Level 1 class of the polygon it falls in. `unesco_year`
   is the UNESCO Global Geopark designation year (UNESCO IGGP pages give the year only).
4. Capitals: the seven national capitals, curated in scripts/capitals.csv (description, camera); the
   coordinates follow the Natural Earth points in docs/data/cities.geojson.
5. Photos: scripts/photos.csv lists one Wikimedia Commons file per geosite id, capital id (cap_<id>) and
   tour stop (tour_<key>, matched by `photo` in STOPS in docs/app.js), with author and licence (CC BY /
   CC BY-SA / public domain only). Each is fetched once (Special:FilePath, 800 px), resized to 720 px and
   saved as docs/img/photos/<id>.jpg; the credit is shown under the photo in the viewer.

Outputs: docs/data/volcanoes.geojson, plates.geojson, geoheritage.geojson, capitals.geojson,
docs/data/photos.json (photo credits for the tour stops) and docs/img/photos/*.jpg
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
PHOTOS = ROOT / "scripts" / "photos.csv"
CAPITALS = ROOT / "scripts" / "capitals.csv"
IMG = ROOT / "docs" / "img" / "photos"
UA = "arabia3d-geology-map/0.1 (https://github.com/kevinalexandr19/arabian-geology-3d)"
LICENCE_URL = {
    "CC BY 2.0": "https://creativecommons.org/licenses/by/2.0/",
    "CC BY 4.0": "https://creativecommons.org/licenses/by/4.0/",
    "CC BY-SA 3.0": "https://creativecommons.org/licenses/by-sa/3.0/",
    "CC BY-SA 4.0": "https://creativecommons.org/licenses/by-sa/4.0/",
    "Public domain": "",
    # Owner-supplied photos (not freely licensed): shown with the credit the owner gave (owner decision, 2026-11-06).
    "Used with credit": "",
}

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


RED_SEA_ISLANDS = {"Tair, Jebel at", "Zubair Group", "Zukur", "Hanish"}  # no or surficial polygon in geo2bg
SNAP_KM = 5        # a field is matched to a Cenozoic-volcanics polygon up to this far from its GVP point
CLUSTER_DEG = 0.02  # volcanics polygons within ~2 km of the field's polygon are highlighted with it
# Owner-chosen map points (lon, lat), used instead of the polygon centre.
POINT_OVERRIDES = {"Kishb, Harrat": (41.3340, 23.1415)}  # crater chain in Harrat Kishb (owner, 2026-11-06)


def volcanoes():
    """GVP Holocene volcanoes, placed on the generalized (1:2M) lava fields so they are easy to spot.

    Each land field is matched to the Cenozoic-volcanics polygon that contains its GVP point (or the nearest
    one within SNAP_KM). The map point is the pole of inaccessibility (most central interior point) of that
    polygon; where several fields share one polygon (Khaybar and Ithnayn), the polygon is first split
    between them by a Voronoi partition of their GVP points. Exceptions: POINT_OVERRIDES; fields inside a
    Yemen-traps polygon (Oligocene, not the Holocene field) keep their GVP point; Red Sea islands and fields
    not mapped at 1:2M keep their GVP point. `pids` lists the polygons the viewer highlights, `bbox` frames
    them. The GVP coordinates stay in gvp_lon/gvp_lat. `mapped`: centred, override, traps, island, not_mapped.
    """
    from shapely import voronoi_polygons
    from shapely.geometry import MultiPoint
    from shapely.ops import polylabel, unary_union

    gj = get(GVP_WFS, "gvp_votw.json")
    geo = json.loads((OUT / "geology.geojson").read_text())["features"]
    vidx = [i for i, f in enumerate(geo) if f["properties"]["level1_class"] == "Cenozoic volcanics"]
    vpolys = [shape(geo[i]["geometry"]) for i in vidx]
    vtree = STRtree(vpolys)
    vprops = [geo[i]["properties"] for i in vidx]

    rows = [f for f in gj["features"] if f["properties"]["Country"] in COUNTRIES]
    match = {}  # GVP name -> index into vpolys
    for f in rows:
        name = f["properties"]["Volcano_Name"]
        pt = Point(f["geometry"]["coordinates"][:2])
        k = vtree.nearest(pt)
        if name not in RED_SEA_ISLANDS and vpolys[k].distance(pt) * 111.2 <= SNAP_KM:
            match[name] = k

    feats = []
    for f in rows:
        p = f["properties"]
        name = p["Volcano_Name"]
        lon, lat = f["geometry"]["coordinates"][:2]
        mx, my, pids, bbox = lon, lat, [], None
        if name in RED_SEA_ISLANDS:
            mapped = "island"
        elif name not in match:
            mapped = "not_mapped"
        else:
            k = match[name]
            poly = vpolys[k]
            label = vprops[k].get("level2_label") or ""
            # the field's polygon plus nearby volcanics (same harrat split by the generalization)
            group = [k] + [m for m in vtree.query(poly.buffer(CLUSTER_DEG))
                           if m != k and vpolys[m].distance(poly) < CLUSTER_DEG
                           and not (vprops[m].get("level2_label") or "").startswith("Yemen traps")]
            if label.startswith("Yemen traps"):
                mapped, group = "traps", []
            else:
                sharers = [g for g, kk in match.items() if kk == k]
                part = poly
                if len(sharers) > 1:  # split the shared polygon between the fields
                    pts = {g: Point(next(r for r in rows if r["properties"]["Volcano_Name"] == g)["geometry"]["coordinates"][:2])
                           for g in sharers}
                    cells = voronoi_polygons(MultiPoint(list(pts.values())), extend_to=poly.envelope.buffer(1))
                    for cell in cells.geoms:
                        if cell.contains(pts[name]):
                            part = poly.intersection(cell)
                    group = [k]
                if part.geom_type == "MultiPolygon":
                    part = max(part.geoms, key=lambda g: g.area)
                if name in POINT_OVERRIDES:
                    mx, my = POINT_OVERRIDES[name]
                    mapped = "override"
                else:
                    c = polylabel(part, tolerance=0.002)
                    mx, my, mapped = c.x, c.y, "centred"
            pids = [vprops[m]["pid"] for m in group]
            if group:
                bbox = [round(v, 3) for v in unary_union([vpolys[m] for m in group]).bounds]
        moved = round(Point(mx, my).distance(Point(lon, lat)) * 111.2, 1)
        feats.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [round(mx, 4), round(my, 4)]},
            "properties": {
                "vnum": p["Volcano_Number"], "name": display_name(name),
                "type": p["Primary_Volcano_Type"], "landform": p["Volcanic_Landform"],
                "rock": p["Major_Rock_Type"], "elev_m": p["Elevation"],
                "last_eruption": p["Last_Eruption_Year"], "evidence": p["Evidence_Category"],
                "note": VOLCANO_NOTES.get(name, ""),
                "mapped": mapped, "moved_km": moved, "gvp_lon": round(lon, 4), "gvp_lat": round(lat, 4),
                "pids": pids, "bbox": bbox,
            },
        })
    # North to south, as listed in the panel.
    feats.sort(key=lambda f: -f["properties"]["gvp_lat"])
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


def photos():
    """Photo per id -> docs/img/photos/<id>.jpg (720 px wide, EXIF stripped) + credit fields.

    Source: a Wikimedia Commons file (`commons_file`), or an owner-supplied image (`local_file`, with the
    credit link in `source_url`). photo_via is "Wikimedia Commons" for Commons files, empty otherwise."""
    from io import BytesIO
    from urllib.parse import quote

    from PIL import Image

    IMG.mkdir(parents=True, exist_ok=True)
    cache = CACHE / "photos"
    cache.mkdir(parents=True, exist_ok=True)
    out = {}
    with PHOTOS.open(newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            if r["licence"] not in LICENCE_URL:
                raise SystemExit(f"{r['id']}: licence {r['licence']!r} not in the allowed list")
            name = r["commons_file"].replace(" ", "_")
            src = cache / f"{r['id']}.src.jpg"
            if r.get("local_file"):  # owner-supplied image committed in data/raw/photos_owner/
                src = ROOT / r["local_file"]
            elif not src.exists():
                url = f"https://commons.wikimedia.org/wiki/Special:FilePath/{quote(name)}?width=800"
                resp = requests.get(url, headers={"User-Agent": UA}, timeout=120)
                resp.raise_for_status()
                src.write_bytes(resp.content)
            dst = IMG / f"{r['id']}.jpg"
            im = Image.open(BytesIO(src.read_bytes())).convert("RGB")
            if im.width > 720:
                im = im.resize((720, round(im.height * 720 / im.width)), Image.LANCZOS)
            im.save(dst, "JPEG", quality=80, optimize=True, progressive=True)
            out[r["id"]] = {
                "photo": f"img/photos/{r['id']}.jpg", "photo_w": im.width, "photo_h": im.height,
                "photo_caption": r["caption"], "photo_author": r["author"], "photo_licence": r["licence"],
                "photo_licence_url": LICENCE_URL[r["licence"]],
                "photo_page": r.get("source_url") or "https://commons.wikimedia.org/wiki/File:" + quote(name),
                "photo_via": "" if r.get("local_file") else "Wikimedia Commons",
            }
    return out


def sites(pics):
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
                               "level1_class": l1,
                               "unesco_year": int(r["unesco_year"]) if r.get("unesco_year") else None,
                               **pics.get(r["id"], {})},
            })
    return feats


def capitals(pics):
    cities = {f["properties"]["name"]: f["geometry"]["coordinates"]
              for f in json.loads((OUT / "cities.geojson").read_text())["features"] if f["properties"].get("capital") == 1}
    feats = []
    with CAPITALS.open(newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            lon, lat = cities.get(r["name"], (float(r["lon"]), float(r["lat"])))
            feats.append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [lon, lat]},
                "properties": {"id": r["id"], "name": r["name"], "country": r["country"], "description": r["description"],
                               "zoom": float(r["zoom"]), "pitch": float(r["pitch"]), "bearing": float(r["bearing"]),
                               **pics.get(f"cap_{r['id']}", {})},
            })
    missing = set(cities) - {f["properties"]["name"] for f in feats}
    if missing:
        raise SystemExit(f"capitals.csv has no row for: {sorted(missing)}")
    return feats


def write(name, feats):
    path = OUT / name
    path.write_text(json.dumps({"type": "FeatureCollection", "features": feats}, ensure_ascii=False,
                               separators=(",", ":")))
    print(f"{name}: {len(feats)} features, {path.stat().st_size / 1024:.1f} KB")


if __name__ == "__main__":
    pics = photos()
    v = volcanoes()
    for f in v:  # volcano photos: photos.csv id volc_<slug>, e.g. volc_rahat
        slug = f["properties"]["name"].split()[-1].lower().replace("'", "")
        f["properties"].update(pics.get(f"volc_{slug}", {}))
    write("volcanoes.geojson", v)
    for f in v:
        p = f["properties"]
        print(f"  {p['name']:<30} last eruption {str(p['last_eruption']):<6} {p['mapped']:<10}"
              f" moved {p['moved_km']:5.1f} km  polygons {len(p['pids']):2d}")
    pl = plates()
    write("plates.geojson", pl)
    s = sites(pics)
    write("geoheritage.geojson", s)
    c = capitals(pics)
    write("capitals.geojson", c)
    tour = {k: v for k, v in pics.items() if k.startswith("tour_")}
    (OUT / "photos.json").write_text(json.dumps(tour, ensure_ascii=False, indent=1))
    print(f"photos: {len(pics)} ({len(tour)} tour stops); capitals with photo: "
          f"{sum('photo' in f['properties'] for f in c)}/{len(c)}")
    for f in s:
        p = f["properties"]
        print(f"  {p['name']:<52} {p['kind']:<8} on: {p['level1_class'] or '(no geology polygon)':<38}"
              f" photo: {p.get('photo_licence', '-')}")
