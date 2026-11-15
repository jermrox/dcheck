"""Full lot scene: terrain from contours, both floors stacked, hip roofs, porches, pool, on the plot plan.

Usage: python3 -I build_lot_scene.py <config.json> <out.html> [site.js]
  site.js (optional): the same scene as data for the Interior Studio "Site" layer (window.LOT_SITE)
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

cfg = json.load(open(sys.argv[1])); out = sys.argv[2]; site_js = sys.argv[3] if len(sys.argv) > 3 else None
FT = cfg.get("ft_per_pt", 60 / 72)
x0, y0, x1, y1 = cfg["clip"]

pg = pymupdf.open(cfg["plot_pdf"])[0]
pix = pg.get_pixmap(dpi=300, clip=pymupdf.Rect(x0, y0, x1, y1))
img = cv2.imdecode(np.frombuffer(pix.tobytes("png"), np.uint8), cv2.IMREAD_COLOR)
ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 80])
ground = {"src": "data:image/jpeg;base64," + base64.b64encode(buf.tobytes()).decode(),
          "x": x0 * FT, "z": y0 * FT, "w": (x1 - x0) * FT, "h": (y1 - y0) * FT}

if cfg.get("lap_pool"):   # replace the plot-plan pool with a lap pool (length x width ft) on the same centre and long axis
    P = np.array(cfg["pool_pt"], float); c = P.mean(0)
    e = [P[(i + 1) % 4] - P[i] for i in range(4)]; u = max(e, key=lambda v: np.hypot(*v)); u = u / np.hypot(*u); v = np.array([-u[1], u[0]])
    L, W = cfg["lap_pool"]["length"] / FT / 2, cfg["lap_pool"]["width"] / FT / 2
    cfg["pool_pt"] = [list(c + su * L * u + sv * W * v) for su, sv in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
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
ROOMCEIL = cfg.get("room_ceilings", {})   # "1|Great Room": 11.08 | "vault" | "tray"; "drop": {"1|Garage": 1.0}
DROP = cfg.get("room_drops", {})

FLOORCOL = {"oak": "#c9a273", "carpet": "#cbc2b2", "bathtile": "#c9d2d6", "concrete": "#b5b2ac", "greytile": "#a9acaf"}
def level(home_path, shift, base, height, lvl, skip_types=("balcony",)):
    home = json.load(open(home_path)); plan = home["plan"]; fin = (home.get("design") or {}).get("finishes", {})
    dx, dz = shift; walls, rooms = [], []
    for w in plan["walls"]:
        ax = w["z1"] == w["z2"]; a0 = min(w["x1"], w["x2"]) if ax else min(w["z1"], w["z2"]); a1 = max(w["x1"], w["x2"]) if ax else max(w["z1"], w["z2"])
        L = a1 - a0
        if L <= 0: continue
        e0 = (a0, w["z1"]) if ax else (w["x1"], a0); e1 = (a1, w["z1"]) if ax else (w["x1"], a1)
        walls.append([P(e0[0] + dx, e0[1] + dz), P(e1[0] + dx, e1[1] + dz),
                      [[round((o["a"] - a0) / L, 4), round((o["b"] - a0) / L, 4), "garage" if o.get("garage") else "bay" if o.get("bay") else o["t"]] for o in w.get("ops", [])]])
    plan_rects = []
    # outline of the level (non-porch rooms) to tell exterior walls from partitions
    G = 0.25; inside = [q for r in plan["rooms"] if r["type"] not in skip_types for q in r["rects"]]
    ox, oz = min(q[0] for q in inside) - 3, min(q[1] for q in inside) - 3
    Wd, Hd = int((max(q[2] for q in inside) - ox + 3) / G) + 1, int((max(q[3] for q in inside) - oz + 3) / G) + 1
    mk = np.zeros((Hd, Wd), np.uint8)
    for q in inside: mk[int((q[1] - oz) / G):int((q[3] - oz) / G), int((q[0] - ox) / G):int((q[2] - ox) / G)] = 1
    mk = cv2.morphologyEx(mk, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    def exterior(e0, e1):
        hits = 0
        for t_ in (0.25, 0.5, 0.75):
            x = e0[0] + (e1[0] - e0[0]) * t_; z = e0[1] + (e1[1] - e0[1]) * t_
            if abs(e1[1] - e0[1]) < 1e-6: a_, b_ = (x, z - 1.2), (x, z + 1.2)
            else: a_, b_ = (x - 1.2, z), (x + 1.2, z)
            va = mk[min(Hd - 1, max(0, int((a_[1] - oz) / G))), min(Wd - 1, max(0, int((a_[0] - ox) / G)))]
            vb = mk[min(Hd - 1, max(0, int((b_[1] - oz) / G))), min(Wd - 1, max(0, int((b_[0] - ox) / G)))]
            hits += int(va != vb)
        return hits >= 2
    for wl, w in zip(walls, [w for w in plan["walls"] if (max(w["x1"], w["x2"]) - min(w["x1"], w["x2"]) if w["z1"] == w["z2"] else max(w["z1"], w["z2"]) - min(w["z1"], w["z2"])) > 0]):
        e0 = (min(w["x1"], w["x2"]), w["z1"]) if w["z1"] == w["z2"] else (w["x1"], min(w["z1"], w["z2"]))
        e1 = (max(w["x1"], w["x2"]), w["z1"]) if w["z1"] == w["z2"] else (w["x1"], max(w["z1"], w["z2"]))
        wl.append(1 if exterior(e0, e1) else 0)
    for r in plan["rooms"]:
        if r["type"] in skip_types: continue
        col = FLOORCOL.get((fin.get(r["id"]) or {}).get("floor"), "#d8d2c6")
        for q in r["rects"]:
            q2 = [q[0] + dx, q[1] + dz, q[2] + dx, q[3] + dz]; plan_rects.append(q2)
            key = f"{lvl}|{r['name']}"; spec = ROOMCEIL.get(key, height); drop = DROP.get(key, 0)
            rooms.append({"name": r["name"], "col": col, "drop": drop, "ceil": spec, "w": q2[2] - q2[0], "d": q2[3] - q2[1],
                          "pts": [P(q2[0], q2[1]), P(q2[2], q2[1]), P(q2[2], q2[3]), P(q2[0], q2[3])]})
    furn = []
    for it in (cfg.get("furniture", {}).get(home_path) or []):
        q = P(it["x"] + dx, it["z"] + dz)
        furn.append({"p": q, "rot": round(math.radians(it.get("rot", 0)) - t, 4), "w": it["w"], "d": it["d"], "h": it["h"],
                     "e": it.get("elev", 0), "c": it.get("color") or "#cccccc", "n": it["type"]})
    return {"base": round(base, 3), "h": height, "walls": walls, "rooms": rooms, "furn": furn}, plan_rects

L1, r1 = level(cfg["level1"]["home"], (0, 0), lv_base[0], ceil[0], 1)
L2, r2 = level(cfg["level2"]["home"], cfg["level2"]["shift"], lv_base[1], ceil[1], 2)

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
gable_pitch = cfg.get("gable_pitch", 1.25)
def roofs(rects, base, blockers=()):
    res = []
    for q in rects:
        q2 = [q[0] - ov, q[1] - ov, q[2] + ov, q[3] + ov]
        # street-facing (largest plan z) if nothing else in this cover sits in front of it across most of its width
        front = not any(o is not q and o[1] >= q[3] - 0.5 and min(o[2], q[2]) - max(o[0], q[0]) > 0.5 * (q[2] - q[0]) for o in list(rects) + list(blockers))
        kind = "front" if front and (q[2] - q[0]) <= 34 else "hip"
        res.append({"base": round(base, 3), "pitch": gable_pitch if kind == "front" else pitch, "kind": kind,
                    "pts": [P(q2[0], q2[1]), P(q2[2], q2[1]), P(q2[2], q2[3]), P(q2[0], q2[3])], "w": q2[2] - q2[0], "d": q2[3] - q2[1]})
    return res
roof2 = roofs(rect_cover(r2), L2["base"] + ceil[1])
roof1 = roofs(rect_cover(r1, exclude=r2), L1["base"] + ceil[0], blockers=r2)

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

def landscape():
    """Paint a realistic ground texture registered to the plot (lawn, driveway, walk, deck, mulch beds, streets)
    and place trees and shrubs. Returns (jpeg data URI, plants). Plants: [x, z, kind, height, radius] in plot feet."""
    K = 300 / 72 * 1.5                                    # px per PDF point (7.5 px per foot)
    W, H = int((x1 - x0) * K), int((y1 - y0) * K)
    rng = np.random.default_rng(7)
    px = lambda pts: np.array([[(a - x0) * K, (b - y0) * K] for a, b in pts], np.int32)
    def poly(pts):
        m = np.zeros((H, W), np.uint8)
        if pts: cv2.fillPoly(m, [px(pts)], 1)
        return m.astype(bool)
    def noise(scale, amp):
        n = rng.standard_normal((H // scale + 2, W // scale + 2)).astype(np.float32)
        return cv2.resize(cv2.GaussianBlur(n, (0, 0), 1.2), (W, H), interpolation=cv2.INTER_CUBIC) * amp
    lot = poly(cfg.get("lot_pt")); drive = poly(cfg.get("driveway_pt")); walk = poly(cfg.get("walk_pt"))
    deck = poly(cfg.get("deck_pt")); pool = poly(cfg["pool_pt"]); house = poly(cfg["footprint_pt"])
    porch = poly(cfg["screen_porch_pt"]) | poly(cfg["summer_porch_pt"])
    # lawn: two greens mixed by large-scale noise, mowing stripes inside the lot, fine grain everywhere
    n1 = noise(60, 1.0); n2 = noise(6, 0.5); fine = rng.standard_normal((H, W)).astype(np.float32) * 0.35
    g1, g2 = np.array([58, 128, 72], np.float32), np.array([44, 104, 60], np.float32)    # BGR
    t = np.clip(0.5 + 0.35 * n1, 0, 1)[..., None]
    img = g1 * (1 - t) + g2 * t
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    stripe = (np.floor((xx * 0.99 + yy * 0.14) / (10 * K / FT * FT * 1.2)) % 2) * 2 - 1
    lotf = cv2.GaussianBlur(lot.astype(np.float32), (0, 0), 3 * K)
    img += ((stripe * 3.5 * lotf)[..., None] + (n2 + fine)[..., None] * 9)
    img = img * (0.88 + 0.12 * lotf)[..., None] + (np.array([30, 60, 40]) * 0.12 * (1 - lotf)[..., None])   # rougher off the lot
    # streets: asphalt between 16 and 42 pt outside the street-side lot lines (east, then the south arc and line)
    road = np.zeros((H, W), bool)
    if cfg.get("lot_pt"):
        lp = np.array(cfg["lot_pt"], float); cen = lp.mean(0)
        chain = lp[2:]                                      # NE corner -> east line -> arc -> south line -> SW corner
        chain = np.vstack([chain[0] + (chain[0] - chain[1]) / np.hypot(*(chain[0] - chain[1])) * 80, chain,
                           chain[-1] + (chain[-1] - chain[-2]) / np.hypot(*(chain[-1] - chain[-2])) * 80])
        def offset(dist):
            out = []
            for i in range(len(chain)):
                a_, b_ = chain[max(0, i - 1)], chain[min(len(chain) - 1, i + 1)]
                tng = (b_ - a_) / np.hypot(*(b_ - a_)); nrm = np.array([-tng[1], tng[0]])
                if np.dot(nrm, chain[i] - cen) < 0: nrm = -nrm
                out.append(chain[i] + nrm * dist)
            return out
        road = poly(offset(16) + offset(42)[::-1]) & ~lot
        img[road] = np.array([70, 72, 74]) + (fine[road] * 10)[:, None]
        for dd_ in (16, 42):
            cv2.polylines(img, [px(offset(dd_))], False, (200, 202, 200), max(2, int(0.6 * K)))
    # mulch beds: 5 ft around the house where nothing else is
    hb = cv2.dilate(house.astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (int(12 * K), int(12 * K)))).astype(bool)
    bed = hb & ~house & ~drive & ~walk & ~porch & ~deck
    img[bed] = np.array([38, 58, 92]) + (fine[bed] * 22)[:, None]                        # dark brown mulch
    def concrete(m, base):
        img[m] = np.array(base, np.float32) + (n2[m] * 10 + fine[m] * 7)[:, None]
    drive &= ~road; concrete(drive, (196, 201, 204)); concrete(walk, (205, 210, 213)); concrete(deck, (186, 200, 210))
    concrete(pool | house | porch, (180, 182, 184))
    # control joints on the driveway every 10 ft
    jm = drive & ((xx + yy * 0.3) % (10 / FT * K) < 1.2)
    img[jm] *= 0.82
    edges = cv2.Canny((drive | walk | deck).astype(np.uint8) * 255, 50, 150) > 0
    img[cv2.dilate(edges.astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool)] *= 0.75
    img = cv2.GaussianBlur(np.clip(img, 0, 255).astype(np.uint8), (0, 0), 0.6)
    if cfg.get("debug_land"): cv2.imwrite(cfg["debug_land"], img)
    ok, b = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 82])
    uri = "data:image/jpeg;base64," + base64.b64encode(b.tobytes()).decode()
    # plants
    plants = []
    keep_out = cv2.dilate((house | porch | pool | deck).astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (int(40 * K), int(40 * K)))).astype(bool)
    hard = drive | walk | (cv2.dilate(drive.astype(np.uint8), np.ones((int(10 * K),) * 2, np.uint8)).astype(bool))
    lot_edge = cv2.distanceTransform(lot.astype(np.uint8), cv2.DIST_L2, 5) / K if lot.any() else np.zeros((H, W))
    road_m = road
    cy_house = np.mean([q[1] for q in cfg["footprint_pt"]])
    for gy in np.arange(4, H - 4, 7 * K):
        for gx in np.arange(4, W - 4, 7 * K):
            X = int(gx + rng.uniform(-3, 3) * K); Y = int(gy + rng.uniform(-3, 3) * K)
            if not (0 <= X < W and 0 <= Y < H) or keep_out[Y, X] or hard[Y, X] or road_m[Y, X]: continue
            ypt = y0 + Y / K; front = ypt > cy_house + 25
            if not lot[Y, X]: pr = 0.0 if front and ypt > 700 else 0.32
            elif lot_edge[Y, X] < 22 and not front: pr = 0.26
            elif front: pr = 0.0 if abs(x0 + X / K - np.mean([q[0] for q in cfg['footprint_pt']])) < 110 else 0.02
            else: pr = 0.05
            if rng.random() < pr:
                kind = "pine" if rng.random() < 0.35 else "oak"
                h = rng.uniform(38, 62) if kind == "pine" else rng.uniform(30, 52)
                plants.append([round((x0 + X / K) * FT, 2), round((y0 + Y / K) * FT, 2), kind, round(h, 1), round(h * (0.2 if kind == "pine" else 0.32), 1)])
    # foundation shrubs and ornamentals along the beds
    fp = cfg["footprint_pt"]
    for i in range(len(fp) - 1):
        a, b = np.array(fp[i]), np.array(fp[i + 1]); L = np.hypot(*(b - a)) * FT
        if L < 4: continue
        u = (b - a) / np.hypot(*(b - a)); nrm = np.array([-u[1], u[0]])
        mid = (a + b) / 2 + nrm * 2
        Xm, Ym = int((mid[0] - x0) * K), int((mid[1] - y0) * K)
        if 0 <= Xm < W and 0 <= Ym < H and house[Ym, Xm]: nrm = -nrm
        for k in np.arange(2.0, L - 1.5, 3.4):
            q = a + u * (k / FT) + nrm * (2.6 / FT)
            Xq, Yq = int((q[0] - x0) * K), int((q[1] - y0) * K)
            if not (0 <= Xq < W and 0 <= Yq < H) or not bed[Yq, Xq]: continue
            kind = "flower" if rng.random() < 0.3 else "bush"
            plants.append([round(q[0] * FT, 2), round(q[1] * FT, 2), kind, round(rng.uniform(2.2, 3.6), 1), round(rng.uniform(1.4, 2.2), 1)])
        if nrm[1] > 0.6 and L > 12:                         # street-facing wall: cypress at its ends
            for q in (a + u * (1.5 / FT) + nrm * (3.2 / FT), b - u * (1.5 / FT) + nrm * (3.2 / FT)):
                Xq, Yq = int((q[0] - x0) * K), int((q[1] - y0) * K)
                if 0 <= Xq < W and 0 <= Yq < H and bed[Yq, Xq]:
                    plants.append([round(q[0] * FT, 2), round(q[1] * FT, 2), "cypress", round(rng.uniform(13, 17), 1), 1.6])
    return uri, plants

land_src, plants = landscape()
ground["land"] = land_src

data = {"ground": ground, "grid": grid, "N": N, "levels": [L1, L2], "roofs": roof1 + roof2, "extras": extras,
        "title": cfg.get("title", "Lot"), "plants": plants, "datum": datum, "ffe": round(ffe, 2)}
def sig(home_path):   # identifies a plan so the Studio knows which level it is showing
    w = json.load(open(home_path))["plan"]["walls"]
    return [len(w)] + [round(v, 2) for x in w[:4] for v in (x["x1"], x["z1"], x["x2"], x["z2"])]
data["fit"] = {k: f1[k] for k in ("rot", "dx", "dy", "mc", "pc")}
data["shift2"] = cfg["level2"]["shift"]
data["sig"] = [sig(cfg["level1"]["home"]), sig(cfg["level2"]["home"])]
here = __file__.replace("build_lot_scene.py", "")
lotjs = open(here + "lot_scene.js").read()
xrjs = open(here + "xr.js").read()
tpl = open(here + "lot_template.html").read().replace("/*LOTJS*/", lotjs).replace("/*XRJS*/", xrjs)
open(out, "w").write(tpl.replace("/*DATA*/null", json.dumps(data)).replace("__TITLE__", cfg.get("title", "Lot")))
if site_js:
    open(site_js, "w").write("window.LOT_SITE = " + json.dumps(data) + ";\n" + lotjs + "\n" + xrjs)
print(f"{out}: FFE {ffe:.1f} ft (grade {grade_min:.1f}-{grade_max:.1f}); walls L1 {len(L1['walls'])}, L2 {len(L2['walls'])}; "
      f"roof planes {len(roof1)}+{len(roof2)}; datum {datum}")
