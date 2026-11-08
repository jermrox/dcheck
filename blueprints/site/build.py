"""Inject blueprints.json into template.html -> index.html (single self-contained page).
Usage: python3 -I build.py <blueprints.json> <template.html> <out.html>"""
import json, re, sys, datetime
src, tpl, out = sys.argv[1:4]
plans, seen, rows = json.load(open(src))["plans"], set(), []
for p in plans:
    if not p.get("sqft") or not p.get("name"):
        continue
    m = re.match(r"https://www\.arhomes\.com/(?:plan/([^/]+)|luxury-simplified/(?:([^/]+)/)?plans/([^/]+))/?$", p["url"] or "")
    if not m:
        continue
    slug = re.sub(r"[^a-z0-9-]", "", (m.group(1) or m.group(3)).lower()) or "plan"
    base, i = slug, 2
    while slug in seen:
        slug, i = f"{base}-{i}", i + 1
    seen.add(slug)
    rows.append({"slug": slug, "n": p["name"], "u": p["url"], "s": p["sqft"], "b": p.get("bedrooms"),
                 "ba": p.get("bathrooms"), "h": p.get("half_baths"), "st": p.get("stories"), "g": p.get("garages"),
                 "pdf": (p["floorplan_pdfs"] or [None])[0], "fp": (p["floorplan_images"] or [None])[0],
                 "ls": "luxury-simplified" in p["url"], "city": (m.group(2) or "").title() or None})
html = open(tpl).read().replace("/*DATA*/[]", json.dumps(rows, separators=(",", ":")))
html = html.replace("__DATE__", datetime.date.today().strftime("%b %d %Y").upper())
open(out, "w").write(html)
print(f"{len(rows)} plans -> {out} ({len(html)//1024} KB)")
