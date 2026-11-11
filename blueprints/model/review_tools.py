"""Measuring tools for the blueprint reviewer agent (see REVIEWER.md).

  python3 -I review_tools.py <root> sheet <base>                  overview image + model summary + OCR'd dimension labels
  python3 -I review_tools.py <root> crop  <base> x0 y0 x1 y1 [zoom]   zoomed crop of the raw blueprint with pixel rulers
  python3 -I review_tools.py <root> span  <base> x y              wall-to-wall distances (px) through point (x, y)

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
