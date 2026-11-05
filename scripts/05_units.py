"""Write docs/data/units.json for the viewer: legend classes and per-GLG unit info.

Reads scripts/geology_classes.csv (GLG -> L1 class, colour, L2 label) and adds an
age range and a short generalized lithology note per GLG code. geo2bg has no
lithology attribute, so LITHOLOGY below is a regional summary compiled for this
map. Edit it here and rerun; the viewer reads only the JSON.

Usage: python scripts/05_units.py
"""

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CLASSES_CSV = ROOT / "scripts" / "geology_classes.csv"
OUT = ROOT / "docs" / "data" / "units.json"

# Legend order: oldest to youngest, then volcanics, then surficial.
L1_ORDER = [
    "Precambrian basement (Arabian Shield)",
    "Paleozoic",
    "Triassic",
    "Jurassic",
    "Cretaceous",
    "Paleogene-Neogene sedimentary",
    "Cenozoic volcanics",
    "Neogene-Quaternary surficial deposits",
]

# GLG -> (age, generalized lithology). Codes present in the peninsula clip only.
UNITS = {
    "pC": ("Precambrian (mainly Neoproterozoic, ~870–540 Ma)",
           "Arc volcanic and volcaniclastic rocks, gneiss, ophiolite belts and granitoid plutons of the Arabian Shield"),
    "PzpC": ("Late Precambrian – early Paleozoic",
             "Late Neoproterozoic to early Paleozoic sedimentary and volcanic rocks and post-orogenic granites, undivided"),
    "Cm": ("Cambrian",
           "Sandstone, minor conglomerate and siltstone"),
    "OCm": ("Cambrian – Ordovician",
            "Sandstone and shale (Saq, Qasim formations)"),
    "DSO": ("Ordovician – Devonian",
            "Sandstone, shale and glacial deposits (Tabuk Formation and equivalents)"),
    "D": ("Devonian",
          "Sandstone and shale (Jauf, Jubah formations)"),
    "P": ("Permian",
          "Shallow-marine limestone and dolomite with clastics (Khuff Formation and equivalents)"),
    "Pz": ("Paleozoic",
           "Sandstone, shale and minor carbonate, undivided"),
    "MzPz": ("Paleozoic – Mesozoic",
             "Sedimentary rocks, undivided"),
    "TrP": ("Permian – Triassic",
            "Limestone, dolomite and shale (Khuff to Sudair formations)"),
    "Tr": ("Triassic",
           "Shale, sandstone and limestone (Sudair, Jilh, Minjur formations)"),
    "JTr": ("Triassic – Jurassic",
            "Sandstone, shale and limestone, undivided"),
    "J": ("Jurassic",
          "Shelf limestone, shale and anhydrite (Marrat, Dhruma, Tuwaiq Mountain, Hanifa, Jubaila, Arab formations)"),
    "KJ": ("Jurassic – Cretaceous",
           "Limestone and sandstone, undivided"),
    "K": ("Cretaceous",
          "Sandstone (Biyadh, Wasia) and limestone (Aruma); in Oman and the UAE also the Semail ophiolite and Hawasina deep-water sediments"),
    "TK": ("Cretaceous – Paleogene",
           "Limestone, marl and shale, undivided"),
    "T": ("Paleogene – Neogene (Paleocene–Pliocene)",
          "Limestone, dolomite, marl, sandstone and evaporites (Umm er Radhuma, Rus, Dammam, Hadrukh, Dam, Hofuf formations)"),
    "TKv": ("Oligocene – Miocene (source code: Tertiary–Cretaceous)",
            "Yemen Volcanic Group: flood basalts and rhyolitic ignimbrites (Yemen traps)"),
    "QTv": ("Oligocene – Quaternary",
            "Alkali olivine basalt lava fields with scoria cones (harrats)"),
    "Qv": ("Quaternary",
           "Basalt lava flows and scoria cones"),
    "TKi": ("Cenozoic (source code: Tertiary–Cretaceous)",
            "Granite, gabbro and dyke swarms related to Red Sea rifting"),
    "Czi": ("Cenozoic",
            "Granite, gabbro and dyke swarms related to Red Sea rifting"),
    "Qe": ("Quaternary",
           "Eolian dune sand (sand seas)"),
    "Qf": ("Quaternary",
           "Alluvial gravel, sand and silt of wadis and fans"),
    "Q": ("Quaternary",
          "Surficial deposits, undivided: alluvium, eolian sand, gravel plains and coastal deposits"),
    "Qsk": ("Quaternary",
            "Sabkha: evaporitic silt and sand with salt crusts"),
    "QT": ("Neogene – Quaternary",
           "Gravel plains, conglomerate and silt"),
}


def main():
    rows = list(csv.DictReader(CLASSES_CSV.open(encoding="utf-8")))
    classes = {}
    units = {}
    for r in rows:
        l1 = r["level1_class"]
        if l1 == "EXCLUDE":
            continue
        c = classes.setdefault(l1, {"name": l1, "colour": r["level1_colour"], "codes": []})
        if c["colour"] != r["level1_colour"]:
            raise SystemExit(f"Inconsistent colour for {l1}")
        code = r["source_unit"]
        if code not in UNITS:
            continue  # not present in the peninsula area
        c["codes"].append(code)
        age, lith = UNITS[code]
        units[code] = {
            "description": r["source_description"],
            "level1_class": l1,
            "age": age,
            "lithology": lith,
        }
    missing = set(UNITS) - set(units)
    if missing:
        raise SystemExit(f"Codes in UNITS but not in CSV: {sorted(missing)}")
    if set(classes) != set(L1_ORDER):
        raise SystemExit(f"L1 classes differ from L1_ORDER: {sorted(classes)}")

    out = {
        "classes": [classes[n] for n in L1_ORDER],
        "units": units,
        "lithology_note": "Generalized regional summary compiled for this map; geo2bg itself has only the age code.",
        "source": {
            "citation": "Pollastro, R.M., Karshbaum, A.S., and Viger, R.J., 1999, Maps showing the geology, oil and gas fields and geologic provinces of the Arabian Peninsula: USGS Open-File Report 97-470B",
            "short": "USGS OFR 97-470B (geo2bg)",
            "doi": "10.3133/ofr97470B",
            "url": "https://doi.org/10.3133/ofr97470B",
        },
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Wrote {OUT.relative_to(ROOT)}: {len(out['classes'])} classes, {len(units)} units")


if __name__ == "__main__":
    main()
