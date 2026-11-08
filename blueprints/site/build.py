"""Inject blueprints.json into template.html -> index.html (single self-contained page).
Usage: python3 -I build.py <blueprints.json> <template.html> <out.html> [fp_dir]
fp_dir: folder of downloaded floor-plan images named <slug>.<ext> (see ../fetch_fp.py)."""
import json, re, sys, datetime, os, glob
src, tpl, out = sys.argv[1:4]
fpdir = sys.argv[4] if len(sys.argv) > 4 else None
BASE = "https://www.arhomes.com/"
plans, seen, rows = json.load(open(src))["plans"], set(), []

def kind_of(path):
    segs = [s for s in path.strip("/").split("/") if s]
    if len(segs) == 2 and segs[0] == "plan": return "plan", None, segs[1]
    if len(segs) >= 3 and segs[0] == "luxury-simplified" and segs[-2] == "plans":
        return "ls", (segs[1].title() if len(segs) == 4 else None), segs[-1]
    if len(segs) == 4 and segs[0] == "builder" and segs[2] == "available-homes": return "avail", segs[1], segs[3]
    if len(segs) == 4 and segs[0] == "builder" and segs[2] == "our-home": return "built", segs[1], segs[3]
    if len(segs) == 2 and segs[0] == "model": return "model", None, segs[1]
    return None, None, None

for p in plans:
    if not p.get("sqft") or not p.get("name") or not (p.get("url") or "").startswith(BASE): continue
    path = p["url"][len(BASE):]
    kind, extra, last = kind_of(path)
    if not kind: continue
    segs = [s for s in path.strip("/").split("/") if s]
    base = (re.sub(r"[^a-z0-9-]", "", last.lower()) if kind in ("plan", "ls")
            else "x-" + re.sub(r"[^a-z0-9-]", "", "-".join(segs[-3:]).lower())) or "plan"
    slug, i = base, 2
    while slug in seen: slug, i = f"{base}-{i}", i + 1
    seen.add(slug)
    img = None
    if fpdir:
        hit = glob.glob(os.path.join(fpdir, base + ".*"))
        img = "fp/" + os.path.basename(hit[0]) if hit else None
    bld = extra.replace("-", " ").title() if kind in ("avail", "built") else None
    rows.append({"slug": slug, "n": p["name"], "u": p["url"], "s": p["sqft"], "b": p.get("bedrooms"),
                 "ba": p.get("bathrooms"), "h": p.get("half_baths"), "st": p.get("stories"), "g": p.get("garages"),
                 "pdf": (p["floorplan_pdfs"] or [None])[0], "fp": (p["floorplan_images"] or [None])[0],
                 "img": img, "k": kind, "city": extra if kind == "ls" else None, "bld": bld})
html = open(tpl).read().replace("/*DATA*/[]", json.dumps(rows, separators=(",", ":")))
html = html.replace("__DATE__", datetime.date.today().strftime("%b %d %Y").upper())
open(out, "w").write(html)
import collections
print(f"{len(rows)} entries -> {out} ({len(html)//1024} KB);", dict(collections.Counter(r['k'] for r in rows)),
      f"images: {sum(1 for r in rows if r['img'])}")
