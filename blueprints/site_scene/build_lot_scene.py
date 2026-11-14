"""Full lot scene: terrain from contours, both floors stacked, hip roofs, porches, pool, on the plot plan.

Usage: python3 -I build_lot_scene.py <config.json> <out.html>
config.json:
  plot_pdf, clip [x0,y0,x1,y1] (PDF pt), ft_per_pt
  level1 {home, fit:{rot,dx,dy,mc,pc}}   plan feet -> plot feet (house footprint fit)
  level2 {home, shift:[dx,dz]}            second floor plan feet -> first floor plan feet
  terrain {deg, coef, mx, scale}          polynomial elevation (ft) in plot feet
  footprint_pt [[x,y],...]                surveyed house outline (PDF pt) for the foundation
  pool_pt [[x,y]*4]; screen_porch_pt [...]; summer_porch_pt [...]; deck_pt [...]
  ceilings [10, 9]; floor_gap 1.0; grade_to_floor 1.5; roof_pitch 0.5; overhang 1.5
"""
import base64, json, math, sys
import pymupdf, cv2, numpy as np

cfg = json.load(open(sys.argv[1])); out = sys.argv[2]
FT = cfg.get("ft_per_pt", 60 / 72)
x0, y0, x1, y1 = cfg["clip"]

pg = pymupdf.open(cfg["plot_pdf"])[0]
pix = pg.get_pixmap(dpi=300, clip=pymupdf.Rect(x0, y0, x1, y1))
img = cv2.imdecode(np.frombuffer(pix.tobytes("png"), np.uint8), cv2.IMREAD_COLOR)
ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 80])
ground = {"src": "data:image/jpeg;base64," + base64.b64encode(buf.tobytes()).decode(),
          "x": x0 * FT, "z": y0 * FT, "w": (x1 - x0) * FT, "h": (y1 - y0) * FT}

T = cfg["terrain"]; MX = np.array(T["mx"])
def elev(x, z):
    p = (np.array([x, z]) - MX) / T["scale"]; cols = [1.0]
    for d in range(1, T["deg"] + 1):
        for i in range(d + 1): cols.append(p[0] ** (d - i) * p[1] ** i)
    return float(np.dot(cols, T["coef"]))
datum = math.floor(min(elev(ground["x"] + i * ground["w"] / 20, ground["z"] + j * ground["h"] / 20) for i in range(21) for j in range(21)))
N = 90
grid = [[round(elev(ground["x"] + i * ground["w"] / N, ground["z"] + j * ground["h"] / N) - datum, 3) for i in range(N + 1)] for j in range(N + 1)]

f1 = cfg["level1"]["fit"]; t = math.radians(f1["rot"]); c, s = math.cos(t), math.sin(t)
def P(x, z):
    u, v = x - f1["mc"][0], z - f1["mc"][1]
    return [round(u * c - v * s + f1["pc"][0] + f1["dx"], 3), round(u * s + v * c + f1["pc"][1] + f1["dy"], 3)]
foot = [[p[0] * FT, p[1] * FT] for p in cfg["footprint_pt"]]
grade_max = max(elev(*p) for p in foot); grade_min = min(elev(*p) for p in foot)
ffe = grade_max + cfg.get("grade_to_floor", 1.5)               # finished floor: above the highest grade at the walls
ceil = cfg.get("ceilings", [10, 9]); gap = cfg.get("floor_gap", 1.0)
lv_base = [ffe - datum, ffe - datum + ceil[0] + gap]

FLOORCOL = {"oak": "#c9a273", "carpet": "#cbc2b2", "bathtile": "#c9d2d6", "concrete": "#b5b2ac", "greytile": "#a9acaf"}
def level(home_path, shift, base, height, skip_types=("balcony",)):
    home = json.load(open(home_path)); plan = home["plan"]; fin = (home.get("design") or {}).get("finishes", {})
    dx, dz = shift; walls, rooms = [], []
    for w in plan["walls"]:
        ax = w["z1"] == w["z2"]; a0 = min(w["x1"], w["x2"]) if ax else min(w["z1"], w["z2"]); a1 = max(w["x1"], w["x2"]) if ax else max(w["z1"], w["z2"])
        L = a1 - a0
        if L <= 0: continue
        e0 = (a0, w["z1"]) if ax else (w["x1"], a0); e1 = (a1, w["z1"]) if ax else (w["x1"], a1)
        walls.append([P(e0[0] + dx, e0[1] + dz), P(e1[0] + dx, e1[1] + dz),
                      [[round((o["a"] - a0) / L, 4), round((o["b"] - a0) / L, 4), o["t"]] for o in w.get("ops", [])]])
    plan_rects = []
    for r in plan["rooms"]:
        if r["type"] in skip_types: continue
        col = FLOORCOL.get((fin.get(r["id"]) or {}).get("floor"), "#d8d2c6")
        for q in r["rects"]:
            q2 = [q[0] + dx, q[1] + dz, q[2] + dx, q[3] + dz]; plan_rects.append(q2)
            rooms.append({"col": col, "pts": [P(q2[0], q2[1]), P(q2[2], q2[1]), P(q2[2], q2[3]), P(q2[0], q2[3])]})
    return {"base": round(base, 3), "h": height, "walls": walls, "rooms": rooms}, plan_rects

L1, r1 = level(cfg["level1"]["home"], (0, 0), lv_base[0], ceil[0])
L2, r2 = level(cfg["level2"]["home"], cfg["level2"]["shift"], lv_base[1], ceil[1])

def rect_cover(rects, exclude=None, G=0.5, min_side=6):
    """Greedy largest-rectangle cover of the union of rects (plan feet), minus 'exclude' rects."""
    xs = [v for q in rects for v in (q[0], q[2])]; zs = [v for q in rects for v in (q[1], q[3])]
    ox, oz = min(xs) - 2, min(zs) - 2; W = int((max(xs) - ox + 2) / G) + 1; H = int((max(zs) - oz + 2) / G) + 1
    m = np.zeros((H, W), np.uint8)
    for q in rects: m[int(round((q[1] - oz) / G)):int(round((q[3] - oz) / G)), int(round((q[0] - ox) / G)):int(round((q[2] - ox) / G))] = 1
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    if exclude:
        for q in exclude:
            e0, e1 = int(round((q[1] - oz) / G)) + 2, int(round((q[3] - oz) / G)) - 2
            f0, f1_ = int(round((q[0] - ox) / G)) + 2, int(round((q[2] - ox) / G)) - 2
            if e1 > e0 and f1_ > f0: m[max(0, e0):max(0, e1), max(0, f0):max(0, f1_)] = 0
    out, k = [], int(min_side / G)
    while m.sum() > k * k:
        best = None; h = np.zeros(W, int)
        for row in range(H):
            h = np.where(m[row] == 1, h + 1, 0); st = []
            for col in range(W + 1):
                hh = h[col] if col < W else 0; start = col
                while st and st[-1][1] >= hh:
                    s0, sh = st.pop(); area = sh * (col - s0)
                    if sh >= k and col - s0 >= k and (best is None or area > best[0]): best = (area, row - sh + 1, s0, row, col - 1)
                    start = s0
                st.append((start, hh))
        if not best: break
        _, ra, ca, rb, cb = best; m[ra:rb + 1, ca:cb + 1] = 0
        out.append([ox + ca * G, oz + ra * G, ox + (cb + 1) * G, oz + (rb + 1) * G])
    return out

pitch, ov = cfg.get("roof_pitch", 0.5), cfg.get("overhang", 1.5)
def roofs(rects, base):
    res = []
    for q in rects:
        q2 = [q[0] - ov, q[1] - ov, q[2] + ov, q[3] + ov]
        res.append({"base": round(base, 3), "pitch": pitch, "pts": [P(q2[0], q2[1]), P(q2[2], q2[1]), P(q2[2], q2[3]), P(q2[0], q2[3])],
                    "w": q2[2] - q2[0], "d": q2[3] - q2[1]})
    return res
roof2 = roofs(rect_cover(r2), L2["base"] + ceil[1])
roof1 = roofs(rect_cover(r1, exclude=r2), L1["base"] + ceil[0])

pt2ft = lambda pts: [[p[0] * FT, p[1] * FT] for p in pts]
def flat(name, pts, z): return {"name": name, "pts": pt2ft(pts), "y": round(z, 3)}
porch_y = ffe - datum - 0.5
extras = {
    "foundation": {"pts": foot, "top": round(ffe - datum, 3), "bottom": round(grade_min - datum - 1, 3)},
    "pool": {"pts": pt2ft(cfg["pool_pt"]), "y": round(elev(*pt2ft(cfg["pool_pt"])[0]) - datum + 0.3, 3)},
    "deck": flat("Pool deck", cfg["deck_pt"], elev(*pt2ft(cfg["deck_pt"])[0]) - datum + 0.25) if cfg.get("deck_pt") else None,
    "screen": {"pts": pt2ft(cfg["screen_porch_pt"]), "y": round(porch_y, 3), "h": 9, "screened": True},
    "summer": {"pts": pt2ft(cfg["summer_porch_pt"]), "y": round(elev(*pt2ft(cfg["summer_porch_pt"])[0]) - datum + 0.3, 3), "h": 9, "screened": False},
}
data = {"ground": ground, "grid": grid, "N": N, "levels": [L1, L2], "roofs": roof1 + roof2, "extras": extras,
        "title": cfg.get("title", "Lot"), "datum": datum, "ffe": round(ffe, 2)}
tpl = open(__file__.replace("build_lot_scene.py", "lot_template.html")).read()
open(out, "w").write(tpl.replace("/*DATA*/null", json.dumps(data)).replace("__TITLE__", cfg.get("title", "Lot")))
print(f"{out}: FFE {ffe:.1f} ft (grade {grade_min:.1f}-{grade_max:.1f}); walls L1 {len(L1['walls'])}, L2 {len(L2['walls'])}; "
      f"roof planes {len(roof1)}+{len(roof2)}; datum {datum}")
