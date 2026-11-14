"""Convert a reader-agent plan (blueprints/model/PLAN_READER.md output, image pixels) into homes for the
Interior Design Visualizer (https://github.com/markiv25/interior_design_visulizer), and verify each one.

Usage: python3 -I to_visualizer.py <plan.json> <blueprint_image> <out_dir> [--title "Obsidian"]
Writes <out_dir>/<slug>-<level>.home.json (import with Homes -> Import in the visualizer) and prints a check report;
also writes <out_dir>/<slug>.report.json. Units in the visualizer are feet; x right, z down the drawing.
"""
import base64, json, math, os, re, statistics, sys
import cv2

WALL_T = 0.5            # visualizer wall thickness, ft
SNAP = 0.35             # same tolerance the visualizer uses to line coordinates up

def feet(txt):
    """Parse one printed dimension such as 14'-7" or 12' 9" -> feet."""
    m = re.match(r"\s*(\d{1,2})\s*'\s*-?\s*(\d{1,2})?", txt or "")
    return int(m.group(1)) + (int(m.group(2)) / 12 if m.group(2) else 0) if m else None

def printed_pair(txt):
    parts = re.split(r"\s*[x×X]\s*", txt or "")
    if len(parts) != 2: return None
    a, b = feet(parts[0]), feet(parts[1])
    return (a, b) if a and b else None

def cluster(vals, tol):
    s = sorted(set(round(v, 2) for v in vals)); out, g = {}, []
    def flush():
        if g:
            m = round(sum(g) / len(g), 2)
            for v in g: out[v] = m
    for v in s:
        if g and v - g[-1] > tol: flush(); g.clear()
        g.append(v)
    flush()
    return lambda v: out.get(round(v, 2), round(v, 2))

def convert_level(lv, ppf, img, title, idx):
    x0, y0, x1, y1 = lv["box"]
    f = lambda px, o: (px - o) / ppf
    walls, rooms = [], []
    for w in lv.get("walls", []):
        wx1, wy1, wx2, wy2 = w[:4]; ops = w[4] if len(w) > 4 else []
        ax = abs(wx2 - wx1) >= abs(wy2 - wy1)
        c = f((wy1 + wy2) / 2, y0) if ax else f((wx1 + wx2) / 2, x0)
        s0, s1 = (f(wx1, x0), f(wx2, x0)) if ax else (f(wy1, y0), f(wy2, y0))
        d = 1 if s1 >= s0 else -1
        o2 = []
        for o in ops:
            p, q = s0 + d * o[1] / ppf, s0 + d * o[2] / ppf
            o2.append({"t": {"opening": "open", "window": "window"}.get(o[0], "door"), "a": min(p, q), "b": max(p, q),
                       "main": bool(len(o) > 3 and o[3])})
        walls.append(dict(ax=ax, c=c, a0=min(s0, s1), a1=max(s0, s1), ops=o2))
    for r in lv.get("rooms", []):
        rects = [[f(min(q[0], q[2]), x0), f(min(q[1], q[3]), y0), f(max(q[0], q[2]), x0), f(max(q[1], q[3]), y0)] for q in r["rect"]]
        rooms.append(dict(name=r["name"][:40], type=r["type"], rects=rects, printed=r.get("printed"), clear_px=r.get("clear_px")))
    xs, zs = [], []
    for w in walls:
        (zs if w["ax"] else xs).append(w["c"]); (xs if w["ax"] else zs).extend([w["a0"], w["a1"]])
    for r in rooms:
        for q in r["rects"]: xs += [q[0], q[2]]; zs += [q[1], q[3]]
    cx, cz = cluster(xs, SNAP), cluster(zs, SNAP)
    out_w, seen = [], set()
    for w in walls:
        c = cz(w["c"]) if w["ax"] else cx(w["c"]); a0 = (cx if w["ax"] else cz)(w["a0"]); a1 = (cx if w["ax"] else cz)(w["a1"])
        if a1 - a0 < 0.3 or (w["ax"], c, a0, a1) in seen: continue
        seen.add((w["ax"], c, a0, a1))
        ops = sorted(({"t": o["t"], "a": round(max(a0 + 0.05, o["a"]), 2), "b": round(min(a1 - 0.05, o["b"]), 2), "main": o["main"]} for o in w["ops"]), key=lambda o: o["a"])
        keep = []
        for o in ops:
            if o["b"] - o["a"] < 0.8 or (keep and o["a"] < keep[-1]["b"] + 0.05): continue
            if o["t"] == "window": o.update(sill=3, head=7)
            if o["t"] == "door": o["hinge"] = "a"
            if not o["main"]: del o["main"]
            keep.append(o)
        out_w.append({"x1": a0, "z1": c, "x2": a1, "z2": c, "ops": keep} if w["ax"] else {"x1": c, "z1": a0, "x2": c, "z2": a1, "ops": keep})
    for r in rooms:
        r["rects"] = [[cx(q[0]), cz(q[1]), cx(q[2]), cz(q[3])] for q in r["rects"]]
        r["rects"] = [q for q in r["rects"] if q[2] - q[0] >= 1 and q[3] - q[1] >= 1]
    rooms = [r for r in rooms if r["rects"]]
    # blueprint underlay, cropped to the level with a margin
    M = int(3 * ppf); H, W = img.shape[:2]
    cx0, cy0, cx1, cy1 = max(0, int(x0) - M), max(0, int(y0) - M), min(W, int(x1) + M), min(H, int(y1) + M)
    crop = img[cy0:cy1, cx0:cx1]
    ok, buf = cv2.imencode(".jpg", crop, [cv2.IMWRITE_JPEG_QUALITY, 82])
    image = {"src": "data:image/jpeg;base64," + base64.b64encode(buf.tobytes()).decode(), "w": crop.shape[1], "h": crop.shape[0],
             "x": (cx0 - x0) / ppf, "z": (cy0 - y0) / ppf, "fpp": 1 / ppf}
    area = round(sum((q[2] - q[0]) * (q[3] - q[1]) for r in rooms for q in r["rects"]))
    beds = sum(1 for r in rooms if r["type"] == "bedroom")
    pid = re.sub(r"[^a-z0-9]+", "-", f"{title}-{lv['name']}".lower()).strip("-")
    plan = {"id": pid, "name": f"{title} · {lv['name']}"[:60], "sub": (f"{beds} bed \u00b7 " if beds else "") + f"{len(rooms)} rooms \u00b7 ~{area} sq.ft",
            "facing": "N", "rooms": [], "walls": out_w, "blocks": [], "image": image}
    used = {}
    for r in rooms:
        pre = {"living": "living", "dining": "dining", "kitchen": "kitchen", "bedroom": "bed", "bath": "bath", "passage": "passage",
               "balcony": "balcony", "utility": "utility", "study": "study", "pooja": "pooja", "store": "store"}.get(r["type"], "room")
        single = r["type"] in ("living", "dining", "kitchen", "passage")
        rid = pre if single and pre not in used else None
        if not rid:
            k = 2 if single else 1
            while f"{pre}{k}" in used: k += 1
            rid = f"{pre}{k}"
        used[rid] = 1
        plan["rooms"].append({"id": rid, "type": r["type"] if r["type"] in ("living", "dining", "kitchen", "bedroom", "bath", "passage", "balcony", "utility", "study", "pooja", "store") else "other",
                              "name": r["name"], "rects": r["rects"]})
    if not any(o.get("main") for w in out_w for o in w["ops"]):          # the app needs one main door
        for w in out_w:
            d = next((o for o in w["ops"] if o["t"] == "door"), None)
            if d: d["main"] = True; break
    return plan, rooms

def check(plan, rooms, lv, ppf):
    rep = {"level": lv["name"], "walls": len(plan["walls"]), "openings": sum(len(w["ops"]) for w in plan["walls"]), "rooms": len(rooms)}
    errs = []
    for r in rooms:                                   # printed size vs modelled clear size (centre lines minus a wall)
        pp = printed_pair(r.get("printed"))
        if not pp: continue
        q = max(r["rects"], key=lambda q: (q[2] - q[0]) * (q[3] - q[1]))
        mw, mh = q[2] - q[0] - WALL_T, q[3] - q[1] - WALL_T
        e = min(max(abs(mw - pp[0]) / pp[0], abs(mh - pp[1]) / pp[1]), max(abs(mw - pp[1]) / pp[1], abs(mh - pp[0]) / pp[0]))
        errs.append((r["name"], round(e * 100, 1), f"{pp[0]:.1f}x{pp[1]:.1f} printed vs {mw:.1f}x{mh:.1f} modelled"))
    rep["room_size_checks"] = len(errs)
    rep["room_size_err_median_pct"] = round(statistics.median(e[1] for e in errs), 1) if errs else None
    rep["room_size_worst"] = sorted(errs, key=lambda e: -e[1])[:3]
    ov = []
    allr = [(r["name"], q) for r in rooms for q in r["rects"]]
    for i in range(len(allr)):
        for j in range(i + 1, len(allr)):
            a, b = allr[i][1], allr[j][1]
            ix = max(0, min(a[2], b[2]) - max(a[0], b[0])) * max(0, min(a[3], b[3]) - max(a[1], b[1]))
            if ix > 1.0 and allr[i][0] != allr[j][0]: ov.append((allr[i][0], allr[j][0], round(ix, 1)))
    rep["room_overlaps"] = ov[:5]; rep["room_overlap_count"] = len(ov)
    def on_wall(x1, z1, x2, z2):                      # fraction of a room edge that has a wall under it
        ax = abs(z1 - z2) < 1e-6; L = abs(x2 - x1) if ax else abs(z2 - z1); cov = 0.0
        for w in plan["walls"]:
            if (w["z1"] == w["z2"]) != ax: continue
            if ax and abs(w["z1"] - z1) <= 0.6: cov += max(0, min(max(x1, x2), max(w["x1"], w["x2"])) - max(min(x1, x2), min(w["x1"], w["x2"])))
            if not ax and abs(w["x1"] - x1) <= 0.6: cov += max(0, min(max(z1, z2), max(w["z1"], w["z2"])) - max(min(z1, z2), min(w["z1"], w["z2"])))
        return min(1, cov / L) if L else 1
    edges = [(q[0], q[1], q[2], q[1]) for _, q in allr] + [(q[0], q[3], q[2], q[3]) for _, q in allr] + [(q[0], q[1], q[0], q[3]) for _, q in allr] + [(q[2], q[1], q[2], q[3]) for _, q in allr]
    rep["room_edges_on_walls_pct"] = round(100 * statistics.mean(on_wall(*e) for e in edges), 1) if edges else None
    living = sum((q[2] - q[0]) * (q[3] - q[1]) for r in rooms if r["type"] not in ("other", "balcony") for q in r["rects"])
    rep["modelled_living_sqft"] = round(living)
    rep["printed_living_sqft"] = lv.get("printed_living_sqft")
    if lv.get("printed_living_sqft"): rep["living_area_diff_pct"] = round((living / lv["printed_living_sqft"] - 1) * 100, 1)
    rep["main_door"] = any(o.get("main") for w in plan["walls"] for o in w["ops"])
    return rep

if __name__ == "__main__":
    args = [a for a in sys.argv[1:]]
    title = "Home"
    if "--title" in args: i = args.index("--title"); title = args[i + 1]; del args[i:i + 2]
    plan_path, img_path, out = args[:3]
    os.makedirs(out, exist_ok=True)
    src, img = json.load(open(plan_path)), cv2.imread(img_path)
    ev = [e for e in src.get("scale_evidence", []) if printed_pair(e.get("printed"))]
    sides = []
    for e in ev:
        a, b = printed_pair(e["printed"]); w, h = e.get("w_px"), e.get("h_px")
        if w and h: sides += [w / a, h / b] if abs(w / a - h / b) < abs(w / b - h / a) else [w / b, h / a]
    report = {"base": src["base"], "px_per_ft": src["px_per_ft"], "scale_sides": len(sides),
              "scale_spread_pct": round((max(sides) - min(sides)) / statistics.median(sides) * 100, 1) if len(sides) > 1 else None,
              "scale_rederived": round(statistics.median(sides), 2) if sides else None, "levels": []}
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    for i, lv in enumerate(src["levels"]):
        ppf = lv.get("px_per_ft") or src["px_per_ft"]
        plan, rooms = convert_level(lv, ppf, img, title, i)
        rep = check(plan, rooms, lv, ppf); report["levels"].append(rep)
        fn = os.path.join(out, f"{slug}-{re.sub(r'[^a-z0-9]+', '-', lv['name'].lower()).strip('-')}.home.json")
        json.dump({"kind": "interior-studio-home", "plan": plan, "design": None}, open(fn, "w"), separators=(",", ":"))
        rep["file"] = os.path.basename(fn)
    json.dump(report, open(os.path.join(out, f"{slug}.report.json"), "w"), indent=1)
    print(json.dumps(report, indent=1))
