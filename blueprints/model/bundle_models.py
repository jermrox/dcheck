"""Bundle per-sheet traced models into one models.json for the site.
Usage: python3 -I bundle_models.py <traced_dir> [<more_dirs>...] <out.json>"""
import json, os, sys
*dirs, out = sys.argv[1:]
models = {}
for d in dirs:
    for f in sorted(os.listdir(d)):
        if f.endswith(".json") and f != "hints.json":
            models[f[:-5]] = json.load(open(os.path.join(d, f)))
json.dump(models, open(out, "w"), separators=(",", ":"))
src = {}
for m in models.values(): src[m.get("src", "?")] = src.get(m.get("src", "?"), 0) + 1
print(f"{len(models)} models -> {out} ({os.path.getsize(out)//1024} KB); scale sources: {src}")
