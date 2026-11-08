"""Turn one AR Homes floor-plan image into a 3D-ready model (walls + scale + floor texture).

Usage: python3 -I model_plan.py <plan.jpg> <x0> <y0> <x1> <y1> <out_dir>
  (x0..y1 = crop box in image pixels around ONE level of the plan)

Output (in out_dir): model.json  {scale_ft_per_px, size_px, walls:[[ [x,y],... ], ...] (polygons, holes included
as separate 'holes' lists), rooms:[{name,x,y,w_ft,h_ft}]}, floor.jpg (cropped drawing used as the floor texture).
"""
import json, os, re, sys
import cv2, numpy as np
from rapidocr_onnxruntime import RapidOCR

img_path, x0, y0, x1, y1, out = sys.argv[1], *map(int, sys.argv[2:6]), sys.argv[6]
os.makedirs(out, exist_ok=True)
img = cv2.imread(img_path)[y0:y1, x0:x1]
g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
H, W = g.shape

# 1. Wall mask: thick dark strokes only (thin lines, text and furniture are removed by the opening).
dark = (g < 90).astype(np.uint8)
walls = cv2.morphologyEx(dark, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5)))
# bridge door/window gaps along each axis, then clean specks
h = cv2.morphologyEx(walls, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, (31, 1)))
v = cv2.morphologyEx(walls, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, (1, 31)))
closed = np.maximum(h, v)
n, lab, stats, _ = cv2.connectedComponentsWithStats(closed, connectivity=8)
keep = np.zeros_like(closed)
for i in range(1, n):
    if stats[i, cv2.CC_STAT_AREA] > 220 and max(stats[i, cv2.CC_STAT_WIDTH], stats[i, cv2.CC_STAT_HEIGHT]) > 30:
        keep[lab == i] = 1
walls = keep

# 2. OCR: room names and printed dimensions.
res, _ = RapidOCR()(img)
texts = [(t, int(np.mean([p[0] for p in b])), int(np.mean([p[1] for p in b])), float(c)) for b, t, c in res]
part_re = re.compile(r"^(\d{1,2})(?:')?(\d{1,2})?\"?'?$")
def parse_part(t):
    m = part_re.match(t)
    if not m: return None
    f = int(m.group(1)) + (int(m.group(2)) / 12 if m.group(2) else 0)
    return f if 5 <= f <= 45 else None
dims = []
for t, x, y, c in texts:
    s_ = t.replace(' ', '').replace('\u00d7', 'x').replace('X', 'x')
    if s_.count('x') == 1:
        pa, pb = (parse_part(q) for q in s_.split('x'))
        if pa and pb: dims.append((x, y, pa, pb))

# 3. Scale: cast rays from each dimension label to the nearest walls (several offsets, median), then
#    accept a room only when BOTH printed sides agree on one ft/px value; take the median over rooms.
def ray(x, y, dx, dy, lim=900):
    for k in range(4, lim):
        xx, yy = x + dx * k, y + dy * k
        if not (0 <= xx < W and 0 <= yy < H): return None
        if walls[yy, xx]: return k
    return None
def span(x, y, ax):
    vals = []
    for off in (-14, -7, 0, 7, 14):
        px, py = (x, y + off) if ax == 0 else (x + off, y)
        a_, b_ = (ray(px, py, -1, 0), ray(px, py, 1, 0)) if ax == 0 else (ray(px, py, 0, -1), ray(px, py, 0, 1))
        if a_ and b_: vals.append(a_ + b_)
    return float(np.median(vals)) if vals else None
cand = []
for x, y, A, B in dims:
    sx, sy = span(x, y, 0), span(x, y, 1)
    if not (sx and sy): continue
    best = min(((abs(A / sx - B / sy) / (A / sx), (A / sx + B / sy) / 2),
                (abs(B / sx - A / sy) / (B / sx), (B / sx + A / sy) / 2)), key=lambda t: t[0])
    if best[0] < 0.10: cand.append(best[1])
cand = np.array(cand)
prior = 1.0 / 7.2
scale = float(np.median(cand)) if len(cand) else prior
spread = float(np.std(cand) / scale) if len(cand) > 2 else None

# 4. Vectorize walls into polygons (outer boundaries + holes).
cnts, hier = cv2.findContours(walls, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
polys = []
for i, c in enumerate(cnts):
    if cv2.contourArea(c) < 40: continue
    a = cv2.approxPolyDP(c, 1.5, True).reshape(-1, 2)
    if len(a) >= 3:
        polys.append({"pts": a.tolist(), "hole": bool(hier[0][i][3] != -1)})

rooms = [{"name": t, "x": x, "y": y} for t, x, y, c in texts
         if re.fullmatch(r"(?i)(master\s*suite|master\s*bath|great\s*room|kitchen|bedroom\s*\d|bath\s*\d?|den|foyer|pantry|utility|laundry|casual\s*dining|dining|cabana|porch|entry\s*porch|garage|study|office|loft|bonus\s*room|mudroom|closet|owner.s\s*suite)", t.strip())]
json.dump({"scale_ft_per_px": scale, "scale_spread": spread, "n_ratio_samples": int(len(cand)), "size_px": [W, H],
           "walls": polys, "rooms": rooms}, open(os.path.join(out, "model.json"), "w"))
cv2.imwrite(os.path.join(out, "floor.jpg"), img, [cv2.IMWRITE_JPEG_QUALITY, 88])
cv2.imwrite(os.path.join(out, "walls.png"), (1 - walls) * 255)
print(f"scale {1/scale:.2f} px/ft (spread {spread}), {len(cand)} samples, {len(polys)} wall polygons, {len(rooms)} rooms, plan {W*scale:.0f} x {H*scale:.0f} ft")
