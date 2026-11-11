"""Apply reviewer-agent findings (review/<base>/review.json) to a bundled models.json.

Usage: python3 -I apply_reviews.py <models.json> <review_dir>
A review's scale is applied only if it re-derives from its own measurements: the median of the listed
per-side px/ft values must be within 2% of the stated px_per_ft, with at least 4 sides and spread under 6%.
Missing walls are added and traced pieces inside an "extra" rectangle are removed; both are approximate.
"""
import json, os, statistics, sys
path, rdir = sys.argv[1], sys.argv[2]
models = json.load(open(path)); report = []
for base in sorted(os.listdir(rdir)):
    f = os.path.join(rdir, base, "review.json")
    if not os.path.exists(f) or base not in models: continue
    r, m = json.load(open(f)), models[base]
    sides = [v for q in r.get("measurements", []) for v in (q.get("ppf_w"), q.get("ppf_h")) if isinstance(v, (int, float))]
    old = 1 / m["s"]; ppf = r.get("px_per_ft"); status = "skipped"
    if ppf and len(sides) >= 4:
        med = statistics.median(sides); spread = (max(sides) - min(sides)) / med * 100
        near = [v for v in sides if abs(v - ppf) / ppf < 0.04]                 # sides that support the stated scale
        if abs(med - ppf) / ppf < 0.02 and spread < 6: status = "reviewed"
        elif len(near) >= 4: status = "mixed"                                   # e.g. levels drawn at different scales
        if status != "skipped":
            m["s"], m["src"] = round(1 / ppf, 5), status
            m["chk"] = None                                     # the area check was computed with the old scale
            m["rv"] = {"n": len(near if status == "mixed" else sides), "spread": round(spread if status == "reviewed" else (max(near) - min(near)) / ppf * 100, 1)}
    add = [q for q in r.get("missing_walls", []) if len(q) == 4 and q[2] > 0 and q[3] > 0]
    ext = [q for q in r.get("extra_walls", []) if len(q) == 4]
    inside = lambda cx, cy: any(x - 4 <= cx <= x + w + 4 and y - 4 <= cy <= y + h + 4 for x, y, w, h in ext)
    before = len(m["w"]) + len(m.get("p", []))
    m["w"] = [q for q in m["w"] if not inside(q[0] + q[2] / 2, q[1] + q[3] / 2)]
    m["p"] = [q for q in m.get("p", []) if not inside(sum(q[0::2]) / (len(q) / 2), sum(q[1::2]) / (len(q) / 2))]
    removed = before - len(m["w"]) - len(m["p"])
    m["w"] += [[int(v) for v in q] for q in add]
    m.setdefault("rv", {}).update({"added": len(add), "removed": removed})
    report.append((base, status, old, ppf, len(sides), len(add), removed))
json.dump(models, open(path, "w"), separators=(",", ":"))
for b, st, old, ppf, n, a, rm in report:
    ch = f"{(ppf / old - 1) * 100:+.1f}%" if ppf else "n/a"
    print(f"{b:16} {st:9} tracer {old:5.2f} -> reviewer {ppf if ppf else float('nan'):5.2f} px/ft ({ch})  sides={n}  walls +{a} -{rm}")
