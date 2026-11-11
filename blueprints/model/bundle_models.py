"""Bundle per-sheet traced models into one models.json for the site.
Usage: python3 -I bundle_models.py <traced_dir> [<more_dirs>...] <out.json>"""
import json, os, sys
*dirs, out = [a for a in sys.argv[1:] if not a.startswith('--')]
models = {}
for d in dirs:
    for f in sorted(os.listdir(d)):
        if f.endswith(".json") and f != "hints.json":
            models[f[:-5]] = json.load(open(os.path.join(d, f)))
import statistics
for m in models.values():                       # older traces stored the area check with the calibration inverted
    if m.get("chk") is not None and m.pop("chk_v", 1) == 1 and "--fix-chk" in sys.argv:
        m["chk"] = None if m.get("src") == "area" else round(m["chk"] * 1.2544 * 1.2544, 2)
good = [1 / m["s"] for m in models.values() if m.get("src") in ("rooms", "room") and 4 <= 1 / m["s"] <= 30]
typical = statistics.median(good) if good else 17.2
fixed = 0
for m in models.values():                       # measured scale that contradicts the published area -> flag it
    if m.get("src") in ("verified", "room") and m.get("chk") and not 0.6 <= m["chk"] <= 1.5: m["src"] = "conflict"
for m in models.values():                       # implausible px-per-foot -> typical value, flagged as not measured
    if not 4 <= 1 / m["s"] <= 30:
        m["s"], m["src"], fixed = round(1 / typical, 5), "default", fixed + 1
print(f"typical scale {typical:.1f} px/ft; replaced {fixed} implausible scales")
json.dump(models, open(out, "w"), separators=(",", ":"))
src = {}
for m in models.values(): src[m.get("src", "?")] = src.get(m.get("src", "?"), 0) + 1
print(f"{len(models)} models -> {out} ({os.path.getsize(out)//1024} KB); scale sources: {src}")
