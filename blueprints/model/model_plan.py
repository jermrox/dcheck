"""Turn one AR Homes floor-plan image into a 3D-ready model: straight wall rectangles, door/window
openings, room labels and a scale estimate.

Usage: python3 -I model_plan.py <plan.jpg> <x0> <y0> <x1> <y1> <out_dir>
  (x0..y1 = crop box in image pixels around ONE level of the plan)

Output (out_dir): model.json, floor.jpg (cropped drawing, used as the floor texture), walls.png (debug).
model.json: scale_ft_per_px, scale_samples, scale_spread, size_px, walls:[{pts,hole}], openings:[{x,y,w,h,kind}],
            rooms:[{name,x,y}]
"""
import json, os, re, sys
import cv2, numpy as np
from rapidocr_onnxruntime import RapidOCR

img_path, x0, y0, x1, y1, out = sys.argv[1], *map(int, sys.argv[2:6]), sys.argv[6]
os.makedirs(out, exist_ok=True)
img = cv2.imread(img_path)[y0:y1, x0:x1]
g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
H, W = g.shape
K = lambda w, h: cv2.getStructuringElement(cv2.MORPH_RECT, (w, h))

# ---- 1. thick dark strokes = walls (thin lines, text, furniture drop out) -----------------------------------
walls = cv2.morphologyEx((g < 90).astype(np.uint8), cv2.MORPH_OPEN, K(5, 5))

# ---- 2. OCR (2x upscale reads digits better) -> room names + printed dimensions ----------------------------
big = cv2.resize(img, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
res, _ = RapidOCR()(big)
texts = [(t, int(np.mean([p[0] for p in b]) / 2), int(np.mean([p[1] for p in b]) / 2)) for b, t, c in (res or [])]
part_re = re.compile(r"^(\d{1,2})(?:')?(\d{1,2})?\"?'?$")
def parse_part(t):
    m = part_re.match(t)
    if not m: return None
    f = int(m.group(1)) + (int(m.group(2)) / 12 if m.group(2) else 0)
    return f if 5 <= f <= 45 else None
dims = []
for t, x, y in texts:
    s_ = t.replace(' ', '').replace('×', 'x').replace('X', 'x')
    if s_.count('x') == 1:
        pa, pb = (parse_part(q) for q in s_.split('x'))
        if pa and pb: dims.append((x, y, pa, pb))

# ---- 3. scale: rays from each dimension label to nearest walls; both printed sides must agree -----------------
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
scale = float(np.median(cand)) if len(cand) else 1 / 17.2          # fallback = typical AR Homes sheet scale
spread = float(np.std(cand) / scale) if len(cand) > 2 else None
ppf = 1 / scale                                                      # pixels per foot

# ---- 4. straight segments: long horizontal / vertical runs -> rectangles ------------------------------------
L = max(18, int(1.4 * ppf))
Hm = cv2.morphologyEx(walls, cv2.MORPH_OPEN, K(L, 1)); Vm = cv2.morphologyEx(walls, cv2.MORPH_OPEN, K(1, L))
def rects(mask):
    n, _, st, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    return [tuple(int(v) for v in st[i, :4]) for i in range(1, n) if st[i, 4] > 40]
hr, vr = rects(Hm), rects(Vm)

# residual (diagonals, columns, fireplaces): thick pixels not explained by the straight runs
resid = walls & (1 - cv2.dilate(np.maximum(Hm, Vm), K(5, 5)))
resid = cv2.morphologyEx(resid, cv2.MORPH_OPEN, K(3, 3))
rcnts, _ = cv2.findContours(resid, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

# ---- 5. bridge collinear gaps, classify each: window (thin lines run across) vs door / cased opening ----------
openings = []
def classify(x, y, w, h, axis):
    band = g[y:y + h, x:x + w] if axis == 'h' else g[y:y + h, x:x + w]
    if band.size == 0: return 'door'
    dark = (band < 140)
    along = dark.any(axis=0).mean() if axis == 'h' else dark.any(axis=1).mean()
    if along > 0.7: return 'window'
    return 'door' if (w if axis == 'h' else h) <= 3.8 * ppf else 'opening'
def bridge(rs, axis):
    key = (lambda r: r[1] + r[3] / 2) if axis == 'h' else (lambda r: r[0] + r[2] / 2)
    thick = (lambda r: r[3]) if axis == 'h' else (lambda r: r[2])
    rs = sorted(rs, key=key); groups = []
    for r in rs:
        for gr in groups:
            if abs(key(gr[0]) - key(r)) <= 4 and abs(thick(gr[0]) - thick(r)) <= 5: gr.append(r); break
        else: groups.append([r])
    for gr in groups:
        gr.sort(key=(lambda r: r[0]) if axis == 'h' else (lambda r: r[1]))
        for a, b in zip(gr, gr[1:]):
            gap = (b[0] - (a[0] + a[2])) if axis == 'h' else (b[1] - (a[1] + a[3]))
            if 0.3 * ppf < gap <= 8 * ppf:
                if axis == 'h': x, y, w, h = a[0] + a[2], int(np.median([a[1], b[1]])), gap, int(np.median([a[3], b[3]]))
                else: x, y, w, h = int(np.median([a[0], b[0]])), a[1] + a[3], int(np.median([a[2], b[2]])), gap
                openings.append({'x': x, 'y': y, 'w': w, 'h': h, 'kind': classify(x, y, w, h, axis), 'axis': axis})
bridge(hr, 'h'); bridge(vr, 'v')

polys = [{'pts': [[x, y], [x + w, y], [x + w, y + h], [x, y + h]], 'hole': False} for x, y, w, h in hr + vr]
for c in rcnts:
    if cv2.contourArea(c) < 60: continue
    a = cv2.approxPolyDP(c, 1.5, True).reshape(-1, 2)
    if len(a) >= 3: polys.append({'pts': a.tolist(), 'hole': False})

rooms = [{'name': t.strip(), 'x': x, 'y': y} for t, x, y in texts
         if re.fullmatch(r"(?i)(master\s*suite|master\s*bath|great\s*room|kitchen|bedroom\s*\d|bath\s*\d?|den|foyer|pantry|utility|laundry|casual\s*dining|dining|cabana|porch|entry\s*porch|garage|study|office|loft|bonus\s*room|mudroom|closet|owner.s\s*suite|arrival|optional\s*patio)", t.strip())]

json.dump({'scale_ft_per_px': scale, 'scale_samples': int(len(cand)), 'scale_spread': spread, 'size_px': [W, H],
           'walls': polys, 'openings': openings, 'rooms': rooms}, open(os.path.join(out, 'model.json'), 'w'))
cv2.imwrite(os.path.join(out, 'floor.jpg'), img, [cv2.IMWRITE_JPEG_QUALITY, 88])
dbg = np.full((H, W, 3), 255, np.uint8)
for p in polys: cv2.fillPoly(dbg, [np.array(p['pts'], np.int32)], (40, 40, 40))
col = {'window': (230, 150, 40), 'door': (60, 60, 220), 'opening': (60, 180, 60)}
for o in openings: cv2.rectangle(dbg, (o['x'], o['y']), (o['x'] + o['w'], o['y'] + o['h']), col[o['kind']], -1)
cv2.imwrite(os.path.join(out, 'walls.png'), dbg)
kinds = {k: sum(1 for o in openings if o['kind'] == k) for k in col}
print(f"scale {ppf:.2f} px/ft ({len(cand)} samples, spread {spread}); {len(polys)} wall pieces; openings {kinds}; "
      f"{len(rooms)} rooms; plan {W*scale:.0f} x {H*scale:.0f} ft")
