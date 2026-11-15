"""Measuring tools for the blueprint reviewer agent (see REVIEWER.md).

  python3 -I review_tools.py <root> sheet <base>                  overview image + model summary + OCR'd dimension labels
  python3 -I review_tools.py <root> crop  <base> x0 y0 x1 y1 [zoom]   zoomed crop of the raw blueprint with pixel rulers
  python3 -I review_tools.py <root> span  <base> x y              wall-to-wall distances (px) through point (x, y)
  python3 -I review_tools.py <root> walls <base> x0 y0 x1 y1       traced walls in a box as merged centre lines (px)
  python3 -I review_tools.py <root> overlay <base> <plan.json> [level]   draw a reader's plan over the blueprint

<root> holds fp/ (blueprint images), traced2/ (models + ocr cache) and review/ (outputs).
All coordinates are pixels of the ORIGINAL blueprint image.
"""
import glob, json, os, sys
import cv2, numpy as np

root, cmd, base = sys.argv[1], sys.argv[2], sys.argv[3]
img_path = glob.glob(os.path.join(root, "fp", base + ".*"))[0]
out_dir = os.path.join(root, "review", base); os.makedirs(out_dir, exist_ok=True)
img = cv2.imread(img_path); H, W = img.shape[:2]
model = json.load(open(os.path.join(root, "traced2", base + ".json")))

def wall_mask():
    m = np.zeros((H, W), np.uint8)
    for x, y, w, h in model["w"]: m[y:y + h, x:x + w] = 1
    for pl in model.get("p", []): cv2.fillPoly(m, [np.array(pl, np.int32).reshape(-1, 2)], 1)
    for x, y, w, h, k in model.get("o", []): m[y:y + h, x:x + w] = 1      # openings count as wall line for measuring
    return m

def rulers(im, x0, y0, zoom, step):
    for gx in range((x0 // step + 1) * step, x0 + im.shape[1] // zoom, step):
        X = (gx - x0) * zoom; cv2.line(im, (X, 0), (X, 14), (0, 0, 255), 2)
        cv2.putText(im, str(gx), (X + 3, 13), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 255), 1, cv2.LINE_AA)
    for gy in range((y0 // step + 1) * step, y0 + im.shape[0] // zoom, step):
        Y = (gy - y0) * zoom; cv2.line(im, (0, Y), (14, Y), (0, 0, 255), 2)
        cv2.putText(im, str(gy), (16, Y + 4), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 255), 1, cv2.LINE_AA)
    return im

if cmd == "sheet":
    ov = img.copy(); red = ov.copy()
    for x, y, w, h in model["w"]: cv2.rectangle(red, (x, y), (x + w, y + h), (40, 40, 230), -1)
    col = [(230, 150, 40), (40, 200, 40), (200, 60, 200)]
    for x, y, w, h, k in model.get("o", []): cv2.rectangle(red, (x, y), (x + w, y + h), col[k], -1)
    ov = cv2.addWeighted(red, 0.6, ov, 0.4, 0)
    ov = rulers(ov, 0, 0, 1, 200)
    p = os.path.join(out_dir, "overview.jpg"); cv2.imwrite(p, ov, [cv2.IMWRITE_JPEG_QUALITY, 85])
    print(f"image {W}x{H}px  overview: {p}")
    print(f"current model: {1/model['s']:.2f} px/ft (source: {model['src']}), {len(model['w'])} wall pieces, {len(model.get('o', []))} openings")
    print("traced walls are red; windows blue, doors green, cased openings magenta; red ruler ticks are every 200 px")
    ocr = os.path.join(root, "traced2", "ocr", base + ".json")
    if os.path.exists(ocr):
        print("OCR text that looks like a dimension (may be misread - verify by cropping):")
        for t, x, y in json.load(open(ocr)):
            if any(ch.isdigit() for ch in t) and ("'" in t or '"' in t or "x" in t.lower() or "×" in t) and y < H * 0.82:
                print(f"  ({x},{y})  {t!r}")
elif cmd == "crop":
    x0, y0, x1, y1 = (int(v) for v in sys.argv[4:8]); zoom = int(sys.argv[8]) if len(sys.argv) > 8 else 3
    x0, y0, x1, y1 = max(0, x0), max(0, y0), min(W, x1), min(H, y1)
    c = cv2.resize(img[y0:y1, x0:x1], None, fx=zoom, fy=zoom, interpolation=cv2.INTER_CUBIC)
    c = rulers(c, x0, y0, zoom, 50 if (x1 - x0) <= 600 else 100)
    p = os.path.join(out_dir, f"crop_{x0}_{y0}_{x1}_{y1}.png"); cv2.imwrite(p, c)
    print(f"crop: {p}   (ruler labels are original-image pixels)")
elif cmd == "span":
    x, y = int(sys.argv[4]), int(sys.argv[5]); m = wall_mask()
    def ray(dx, dy):
        for n in range(2, 2500):
            xx, yy = x + dx * n, y + dy * n
            if not (0 <= xx < W and 0 <= yy < H): return None
            if m[yy, xx]: return n
        return None
    l, r, u, d = ray(-1, 0), ray(1, 0), ray(0, -1), ray(0, 1)
    print(f"from ({x},{y}): left={l} right={r} up={u} down={d}  ->  width_px={(l + r) if l and r else None}  height_px={(u + d) if u and d else None}")
    print("None means no traced wall was hit in that direction (a missing wall or an open side); measure from a crop instead.")
elif cmd == "walls":
    x0, y0, x1, y1 = (int(v) for v in sys.argv[4:8])
    segs = []
    for x, y, w, h in model["w"]:
        if x + w < x0 or x > x1 or y + h < y0 or y > y1: continue
        segs.append(("h", y + h / 2, x, x + w, h) if w >= h else ("v", x + w / 2, y, y + h, w))
    out = []
    for ax in ("h", "v"):                                     # merge collinear pieces with small gaps
        group = sorted((s_ for s_ in segs if s_[0] == ax), key=lambda q: (round(q[1] / 4), q[2]))
        cur = None
        for q in group:
            if cur and abs(q[1] - cur[1]) <= 4 and q[2] - cur[3] <= 6: cur = [ax, (cur[1] + q[1]) / 2, cur[2], max(cur[3], q[3]), max(cur[4], q[4])]
            else:
                if cur: out.append(cur)
                cur = list(q)
        if cur: out.append(cur)
    for ax, c, a, b, t in sorted(out, key=lambda q: (q[0], q[1], q[2])):
        if b - a < 12: continue
        print(f"{ax} " + (f"y={c:.0f} x={a:.0f}..{b:.0f}" if ax == "h" else f"x={c:.0f} y={a:.0f}..{b:.0f}") + f" thick={t:.0f}")
    gaps = [o for o in model.get("o", []) if x0 <= o[0] <= x1 and y0 <= o[1] <= y1]
    print("traced openings (x,y,w,h,kind 0 window/1 door/2 opening):", gaps)
elif cmd == "overlay":
    plan = json.load(open(sys.argv[4])); lv_i = int(sys.argv[5]) if len(sys.argv) > 5 else None
    ov = img.copy(); col = {"door": (40, 170, 40), "window": (230, 140, 30), "opening": (200, 60, 200)}
    for i, lv in enumerate(plan.get("levels", [])):
        if lv_i is not None and i != lv_i: continue
        for r in lv.get("rooms", []):
            for q in r["rect"]:
                cv2.rectangle(ov, (int(q[0]), int(q[1])), (int(q[2]), int(q[3])), (60, 200, 255), 2)
            q = r["rect"][0]; cv2.putText(ov, f"{r['name']} [{r['type']}]", (int(q[0]) + 4, int(q[1]) + 16), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 90, 200), 1, cv2.LINE_AA)
        for w in lv.get("walls", []):
            x1_, y1_, x2_, y2_ = (int(v) for v in w[:4]); cv2.line(ov, (x1_, y1_), (x2_, y2_), (30, 30, 230), 3)
            L = max(1e-6, ((x2_ - x1_) ** 2 + (y2_ - y1_) ** 2) ** 0.5); ux, uy = (x2_ - x1_) / L, (y2_ - y1_) / L
            for o in (w[4] if len(w) > 4 else []):
                a, b = o[1], o[2]
                cv2.line(ov, (int(x1_ + ux * a), int(y1_ + uy * a)), (int(x1_ + ux * b), int(y1_ + uy * b)), col.get(o[0], (0, 0, 0)), 6)
        if "box" in lv: cv2.rectangle(ov, tuple(int(v) for v in lv["box"][:2]), tuple(int(v) for v in lv["box"][2:]), (120, 120, 120), 1)
    ov = rulers(ov, 0, 0, 1, 200)
    p = os.path.join(out_dir, "overlay.jpg" if lv_i is None else f"overlay_{lv_i}.jpg"); cv2.imwrite(p, ov, [cv2.IMWRITE_JPEG_QUALITY, 88])
    print(f"overlay: {p}  (red = your walls, green doors, orange windows, magenta openings, yellow boxes = rooms)")
