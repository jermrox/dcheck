"""Build a 3D site scene: a traced house placed on a surveyor's plot plan.

Usage: python3 -I build_site.py <plot.pdf> <home.json> <house_fit.json> <out.html> [--pool x1,y1,x2,y2,x3,y3,x4,y4] [--title T]
  plot.pdf        CAD-exported plot plan (vector); scale from --ft-per-pt (default 60/72: 1" = 60')
  home.json       Interior Design Visualizer home (first floor) whose walls get extruded
  house_fit.json  {"rot": deg, "dx": ft, "dy": ft, "mc": [x, z], "pc": [x, y]} mapping plan ft -> plot ft
  --pool          pool coping corners in PDF points (clockwise)
The plot is rendered as the ground texture at true scale, the house walls stand on it at the fitted pose,
rooms get floor colours from the home's design finishes, and the pool is cut in as water.
"""
import argparse, base64, json, math
import pymupdf, cv2, numpy as np

ap = argparse.ArgumentParser()
ap.add_argument("pdf"); ap.add_argument("home"); ap.add_argument("fit"); ap.add_argument("out")
ap.add_argument("--pool"); ap.add_argument("--title", default="Site"); ap.add_argument("--ft-per-pt", type=float, default=60 / 72)
ap.add_argument("--clip", default="215,405,505,740", help="PDF-point box of the lot to render")
a = ap.parse_args()
FT = a.ft_per_pt
x0, y0, x1, y1 = (float(v) for v in a.clip.split(","))

# ground: the plot itself, rendered at 300 dpi inside the clip box
pg = pymupdf.open(a.pdf)[0]
pix = pg.get_pixmap(dpi=300, clip=pymupdf.Rect(x0, y0, x1, y1))
img = cv2.imdecode(np.frombuffer(pix.tobytes("png"), np.uint8), cv2.IMREAD_COLOR)
ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 80])
ground = {"src": "data:image/jpeg;base64," + base64.b64encode(buf.tobytes()).decode(),
          "x": x0 * FT, "z": y0 * FT, "w": (x1 - x0) * FT, "h": (y1 - y0) * FT}

fit = json.load(open(a.fit)); t = math.radians(fit["rot"]); c, s = math.cos(t), math.sin(t)
mc, pc = fit["mc"], fit["pc"]
def P(x, z):  # plan feet -> plot feet
    u, v = x - mc[0], z - mc[1]
    return [round(u * c - v * s + pc[0] + fit["dx"], 3), round(u * s + v * c + pc[1] + fit["dy"], 3)]

home = json.load(open(a.home)); plan = home["plan"]; fin = (home.get("design") or {}).get("finishes", {})
walls = []
for w in plan["walls"]:
    ax = w["z1"] == w["z2"]; a0, a1 = (min(w["x1"], w["x2"]), max(w["x1"], w["x2"])) if ax else (min(w["z1"], w["z2"]), max(w["z1"], w["z2"]))
    L = a1 - a0
    if L <= 0: continue
    p0 = P(w["x1"], w["z1"]) if (w["x1"] if ax else w["z1"]) == a0 else P(w["x2"], w["z2"])
    p1 = P(w["x2"], w["z2"]) if p0 == P(w["x1"], w["z1"]) else P(w["x1"], w["z1"])
    ops = [[round((o["a"] - a0) / L, 4), round((o["b"] - a0) / L, 4), o["t"]] for o in w.get("ops", [])]
    walls.append([p0, p1, ops])
FLOORCOL = {"oak": "#c9a273", "carpet": "#cbc2b2", "bathtile": "#c9d2d6", "concrete": "#b5b2ac", "greytile": "#a9acaf",
            "marble": "#efe9df", "vitrified": "#e6ddcf", "terrazzo": "#e5dfd5", "walnut": "#7a5536"}
rooms = []
for r in plan["rooms"]:
    col = FLOORCOL.get((fin.get(r["id"]) or {}).get("floor"), "#d8d2c6")
    for q in r["rects"]:
        rooms.append({"name": r["name"], "col": col, "pts": [P(q[0], q[1]), P(q[2], q[1]), P(q[2], q[3]), P(q[0], q[3])]})
pool = None
if a.pool:
    v = [float(x) * FT for x in a.pool.split(",")]; pool = [[v[i], v[i + 1]] for i in range(0, 8, 2)]

data = {"ground": ground, "walls": walls, "rooms": rooms, "pool": pool, "title": a.title}
html = open(__file__.replace("build_site.py", "site_template.html")).read().replace("/*DATA*/null", json.dumps(data))
html = html.replace("__TITLE__", a.title)
open(a.out, "w").write(html)
print(f"{a.out}: {len(walls)} walls, {len(rooms)} floor areas, pool={'yes' if pool else 'no'}, {len(html) // 1024} KB")
