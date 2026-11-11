"""Batch-trace AR Homes floor-plan sheets into 3D-ready wall models.

Usage: python3 -I trace_all.py <fp_dir> <out_dir> [name ...]     (no names = every image in fp_dir)
Writes <out_dir>/<image-basename>.json per sheet and, with --debug, <basename>.png overlays.

Per sheet: thick dark strokes -> straight wall rectangles; collinear gaps are classified as window / door /
opening from what is drawn in the gap; scale (ft per px) comes from printed room dimensions when at least one
room's two sides agree, else a default for the sheet size (flagged in "conf").
Compact output: {"size":[W,H], "s":ft_per_px, "conf":n_rooms_used, "w":[[x,y,w,h],...], "p":[[x1,y1,...],...],
                 "o":[[x,y,w,h,k],...]}   k: 0 window, 1 door, 2 cased opening
"""
import json, os, re, sys
import cv2, numpy as np

DEBUG = "--debug" in sys.argv
args = [a for a in sys.argv[1:] if a != "--debug"]
fp_dir, out_dir, names = args[0], args[1], args[2:]
# optional hints: <out_dir>/hints.json  {image-basename: enclosed area in sq ft (living + garage)}
HINTS = json.load(open(os.path.join(out_dir, "hints.json"))) if os.path.exists(os.path.join(out_dir, "hints.json")) else {}
os.makedirs(out_dir, exist_ok=True)
K = lambda w, h: cv2.getStructuringElement(cv2.MORPH_RECT, (max(1, int(w)), max(1, int(h))))
part_re = re.compile(r"^(\d{1,2})(?:')?(\d{1,2})?\"?'?$")
_ocr = None

def parse_part(t):
    m = part_re.match(t)
    if not m: return None
    inch = int(m.group(2)) if m.group(2) else 0
    f = int(m.group(1)) + (inch / 12 if inch <= 11 else 0.5)      # misread inches -> middle of the foot
    return f if 5 <= f <= 45 else None

def trace(path, area_ft2=None, ksz=5):
    global _ocr
    img = cv2.imread(path)
    if img is None: return None
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY); H, W = g.shape
    k = W / 1700.0                                              # sheets come in a few sizes; kernels follow
    dark = (g < 90).astype(np.uint8)
    walls = cv2.morphologyEx(dark, cv2.MORPH_OPEN, K(round(ksz * k), round(ksz * k)))
    thin0 = cv2.morphologyEx(dark, cv2.MORPH_OPEN, K(round(3 * k), round(3 * k)))
    if ksz == 5 and walls.sum() < 0.42 * thin0.sum(): return trace(path, area_ft2, ksz=3)   # big home drawn small
    if ksz == 5:                                                # thinner walls: keep 3px strokes only where they run long and straight
        thin = cv2.morphologyEx(dark, cv2.MORPH_OPEN, K(round(3 * k), round(3 * k)))
        walls |= cv2.morphologyEx(thin, cv2.MORPH_OPEN, K(round(46 * k), 1)) | cv2.morphologyEx(thin, cv2.MORPH_OPEN, K(1, round(46 * k)))
    walls[: int(H * 0.11), int(W * 0.76):] = 0                  # AR Homes logo, top right
    walls[int(H * 0.80):, :] = 0                                # title block / spec table strip

    # --- printed dimensions (OCR at 2x, cached per sheet) ---
    cache = os.path.join(out_dir, "ocr", os.path.splitext(os.path.basename(path))[0] + ".json")
    if os.path.exists(cache): texts = json.load(open(cache))
    else:
        if _ocr is None:
            from rapidocr_onnxruntime import RapidOCR
            _ocr = RapidOCR()
        big = cv2.resize(img, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
        res, _ = _ocr(big)
        texts = [[t, int(np.mean([q[0] for q in b_]) / 2), int(np.mean([q[1] for q in b_]) / 2)] for b_, t, c in (res or [])]
        os.makedirs(os.path.dirname(cache), exist_ok=True); json.dump(texts, open(cache, "w"))
    dims, overall = [], []
    for t, x, y in texts:
        s_ = t.replace(' ', '').replace('-', '').replace('×', 'x').replace('X', 'x')
        if s_.count('x') == 1:
            pa, pb = (parse_part(q) for q in s_.split('x'))
            if pa and pb: dims.append((x, y, pa, pb))
        elif y < H * 0.80:
            m_ = re.match(r"^(\d{2,3})'?(\d{1,2})?\"?$", s_)       # lone label such as 59'8": an overall width or depth
            if m_ and 20 <= int(m_.group(1)) <= 220 and (not m_.group(2) or int(m_.group(2)) <= 11):
                overall.append(int(m_.group(1)) + (int(m_.group(2)) / 12 if m_.group(2) else 0))
    def ray(x, y, dx, dy, lim=int(900 * k)):
        for n in range(4, lim):
            xx, yy = x + dx * n, y + dy * n
            if not (0 <= xx < W and 0 <= yy < H): return None
            if walls[yy, xx]: return n
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
        if best[0] < 0.07: cand.append(best[1])
    default = 1 / 17.2                                           # AR Homes sheets are often drawn near 17 px per foot
    cand = [c for c in cand if default * 0.3 < c < default * 3.0]
    if len(cand) >= 2:                                            # keep the readings that agree with the median
        med = float(np.median(cand)); agree = [c for c in cand if abs(c - med) / med < 0.10]
        cand = agree if len(agree) >= 2 else cand[:1]

    def extract(ppf):
        """straight wall rectangles, residual shapes and classified openings for a given px-per-foot"""
        L = max(18, int(1.4 * ppf))
        Hm = cv2.morphologyEx(walls, cv2.MORPH_OPEN, K(L, 1)); Vm = cv2.morphologyEx(walls, cv2.MORPH_OPEN, K(1, L))
        def rects(mask):
            n, _, st, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
            return [tuple(int(v) for v in st[i, :4]) for i in range(1, n) if st[i, 4] > 40 * k]
        hr, vr = rects(Hm), rects(Vm)
        resid = walls & (1 - cv2.dilate(np.maximum(Hm, Vm), K(5, 5)))
        resid = cv2.morphologyEx(resid, cv2.MORPH_OPEN, K(3, 3))
        rcnts, _ = cv2.findContours(resid, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        polys = []
        for c in rcnts:
            if cv2.contourArea(c) < 60 * k * k: continue
            a_ = cv2.approxPolyDP(c, 1.5, True).reshape(-1, 2)
            if len(a_) >= 3: polys.append([int(v) for v in a_.flatten()])
        openings = []
        def classify(x, y, w, h, axis):
            band = g[y:y + h, x:x + w]
            if band.size == 0: return 1
            dark = band < 140
            along = dark.any(axis=0).mean() if axis == 'h' else dark.any(axis=1).mean()
            if along > 0.7: return 0
            return 1 if (w if axis == 'h' else h) <= 3.8 * ppf else 2
        def bridge(rs, axis):
            key = (lambda r: r[1] + r[3] / 2) if axis == 'h' else (lambda r: r[0] + r[2] / 2)
            thick = (lambda r: r[3]) if axis == 'h' else (lambda r: r[2])
            groups = []
            for r in sorted(rs, key=key):
                for gr in groups:
                    if abs(key(gr[0]) - key(r)) <= 4 * k and abs(thick(gr[0]) - thick(r)) <= 5 * k: gr.append(r); break
                else: groups.append([r])
            for gr in groups:
                gr.sort(key=(lambda r: r[0]) if axis == 'h' else (lambda r: r[1]))
                for a_, b_ in zip(gr, gr[1:]):
                    gap = (b_[0] - (a_[0] + a_[2])) if axis == 'h' else (b_[1] - (a_[1] + a_[3]))
                    if 0.3 * ppf < gap <= 8 * ppf:
                        if axis == 'h': x, y, w, h = a_[0] + a_[2], int(np.median([a_[1], b_[1]])), gap, int(np.median([a_[3], b_[3]]))
                        else: x, y, w, h = int(np.median([a_[0], b_[0]])), a_[1] + a_[3], int(np.median([a_[2], b_[2]])), gap
                        openings.append([int(x), int(y), int(w), int(h), classify(x, y, w, h, axis)])
        bridge(hr, 'h'); bridge(vr, 'v')
        return hr, vr, polys, openings

    prov = float(np.median(cand)) if cand else default
    hr, vr, polys, openings = extract(1 / prov)
    # outline-area estimate: filled outline of every traced level vs published square footage
    area_scale = None
    if area_ft2:
        mk = np.zeros((H, W), np.uint8)
        for x, y, w, h in hr + vr: mk[y:y + h, x:x + w] = 1
        for x, y, w, h, kd in openings: mk[y:y + h, x:x + w] = 1
        dl = cv2.dilate(mk, K(round(52 * k), round(52 * k)))
        cs, _ = cv2.findContours(dl, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        fill = sum(cv2.contourArea(c) for c in cs if cv2.contourArea(c) > 20000 * k * k)
        if fill > 0: area_scale = float(np.sqrt(area_ft2 / fill)) / 1.12       # 1.12: calibration vs room-verified sheets
    # votes: every printed room side and every overall label proposes a ft-per-px value; agreement wins
    hyps = []                                                      # (value, source id, weight)
    for i, (x, y, A, B) in enumerate(dims):
        sx, sy = span(x, y, 0), span(x, y, 1)
        if sx and sy:
            for u, v in ((A, B), (B, A)):
                if abs(u / sx - v / sy) / (u / sx) < 0.07: hyps.append(((u / sx + v / sy) / 2, ('r', i), 2)); break
            else:
                for f in (A, B): hyps += [(f / sx, ('r', i), .5), (f / sy, ('r', i), .5)]
        elif sx or sy:
            for f in (A, B): hyps.append((f / (sx or sy), ('r', i), .5))
    if overall:
        mk2 = np.zeros((H, W), np.uint8)
        for x, y, w, h in hr + vr: mk2[y:y + h, x:x + w] = 1
        pad = round(26 * k); dl2 = cv2.dilate(mk2, K(2 * pad, 2 * pad))
        cs2, _ = cv2.findContours(dl2, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        ext = [d for c in cs2 if cv2.contourArea(c) > 20000 * k * k for d in (cv2.boundingRect(c)[2] - 2 * pad, cv2.boundingRect(c)[3] - 2 * pad)]
        for j, f in enumerate(overall):
            for e in ext:
                if e > 60: hyps.append((f / e, ('o', j), 1))
    hyps = [h for h in hyps if 1 / 40 < h[0] < 1 / 4]
    best = (0, None, False); weak = (0, None)
    for c, _, _ in hyps:
        sup = {}
        for v, sid, wt in hyps:
            if abs(v - c) / c < 0.05: sup[sid] = max(sup.get(sid, 0), wt)
        score = sum(sup.values())
        ok = (not area_scale) or 0.62 < c / area_scale < 1.6
        if ok and score > weak[0]: weak = (score, float(np.median([v for v, sid, wt in hyps if abs(v - c) / c < 0.05])))
        if ok and (2 in sup.values(), score) > (best[2], best[0]):
            best = (score, float(np.median([v for v, sid, wt in hyps if abs(v - c) / c < 0.05 and wt == max(sup.values())])), 2 in sup.values())
    votes = best[0]
    if votes >= 3 and best[2]: scale, src = best[1], 'verified'                 # three or more independent dimensions agree
    elif len(cand) >= 2: scale, src = float(np.median(cand)), 'rooms'
    elif weak[0] >= 3 and area_scale and abs(weak[1] / area_scale - 1) < 0.12: scale, src, votes = weak[1], 'rooms', weak[0]
    elif votes >= 2 and best[1] and best[2]: scale, src = best[1], 'room'
    elif cand and (not area_scale or 0.7 < cand[0] / area_scale < 1.3): scale, src = cand[0], 'room'
    elif area_scale: scale, src = area_scale, 'area'
    else: scale, src = default, 'default'
    if abs(scale / prov - 1) > 0.25: hr, vr, polys, openings = extract(1 / scale)
    ppf = 1 / scale

    if ksz == 5 and len(hr) + len(vr) < 45:                      # big home drawn small: walls are thin, retry finer
        return trace(path, area_ft2, ksz=3)
    model = {"size": [W, H], "s": round(scale, 5), "conf": int(votes), "src": src, "chk": (round(fill * scale * scale * 1.2544 / area_ft2, 2) if area_ft2 and area_scale and src != 'area' else None), "w": [list(r) for r in hr + vr], "p": polys, "o": openings}
    if DEBUG:
        dbg = img.copy()
        for x, y, w, h in hr + vr: cv2.rectangle(dbg, (x, y), (x + w, y + h), (40, 40, 220), -1)
        for pl in polys: cv2.fillPoly(dbg, [np.array(pl, np.int32).reshape(-1, 2)], (40, 40, 220))
        col = [(230, 150, 40), (40, 200, 40), (200, 60, 200)]
        for x, y, w, h, kd in openings: cv2.rectangle(dbg, (x, y), (x + w, y + h), col[kd], -1)
        cv2.imwrite(os.path.join(out_dir, os.path.splitext(os.path.basename(path))[0] + ".png"), dbg)
    return model

def run(name):
    out = os.path.join(out_dir, os.path.splitext(name)[0] + ".json")
    if os.path.exists(out) and not DEBUG: return name, "skip"
    try:
        m = trace(os.path.join(fp_dir, name), HINTS.get(os.path.splitext(name)[0]))
        if m is None: return name, "unreadable"
        json.dump(m, open(out, "w"), separators=(",", ":"))
        return name, f"walls={len(m['w'])} openings={len(m['o'])} conf={m['conf']} src={m['src']} ppf={1/m['s']:.1f} plan={m['size'][0]*m['s']:.0f}x{m['size'][1]*m['s']:.0f}ft"
    except Exception as e:                                        # keep the batch going; report at the end
        return name, f"ERROR {type(e).__name__}: {e}"

if __name__ == "__main__":
    todo = names or sorted(f for f in os.listdir(fp_dir) if f.lower().endswith((".jpg", ".jpeg", ".png", ".webp")))
    for n in todo: print(*run(n), flush=True)          # one at a time: the OCR already uses every core
    print("TRACEDONE", flush=True)
