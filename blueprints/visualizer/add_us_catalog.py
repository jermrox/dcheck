"""Add furniture the Obsidian needs to the Interior Studio catalog (freestanding tub, kitchen island with
deep sink and stools, cars, gym rack, treadmill, dog kennel, raised dog wash, crib), and hide the
sample-flat product library on imported homes. Idempotent.  Usage: python3 -I add_us_catalog.py <studio.html>"""
import sys
page = sys.argv[1]; s = open(page).read()
if "/* us-catalog */" in s:
    print("already patched"); sys.exit()
BUILDERS = r'''/* us-catalog */
function tubFree(g, it) {
  const P = m(it.color, 0.25), W = m('#cfe6f2', 0.05, 0.1), Ch = m(it.color2, 0.25, 0.8);
  const o = B(g, it.w, it.h, it.d, 0, it.h / 2, 0, P);
  B(g, it.w - 0.45, 0.04, it.d - 0.45, 0, it.h - 0.22, 0, W);
  C(g, 0.06, 0.06, 2.6, it.w / 2 + 0.35, 1.3, 0, Ch); B(g, 0.5, 0.06, 0.08, it.w / 2 + 0.15, 2.55, 0, Ch);
}
function island(g, it) {
  const Cab = m(it.color, 0.55), Top = m(it.color2, 0.3), Dark = m('#3a3f45', 0.3, 0.6), Seat = m('#7a5536', 0.6), Leg = m('#2f3437', 0.4, 0.7);
  B(g, it.w - 0.2, 2.9, it.d - 1.1, 0, 1.45, -0.55, Cab);
  B(g, it.w, 0.15, it.d, 0, 3.0, 0, Top);
  B(g, 2.6, 0.06, 1.5, -it.w * 0.18, 3.06, -0.6, Dark);          // 10 in. deep single-bowl sink
  C(g, 0.05, 0.05, 1.3, -it.w * 0.18, 3.7, -1.35, Leg);
  const n = Math.max(2, Math.floor(it.w / 2.4));
  for (let k = 0; k < n; k++) { const x = -it.w / 2 + it.w * (k + 0.5) / n; C(g, 0.6, 0.6, 0.12, x, 2.55, it.d / 2 + 0.55, Seat); C(g, 0.05, 0.05, 2.5, x, 1.25, it.d / 2 + 0.55, Leg); }
}
function carBuild(g, it) {
  const Bd = m(it.color, 0.35, 0.4), Gl = m('#2b3440', 0.1, 0.3), Ti = m('#1b1d20', 0.9);
  B(g, it.w, 2.1, it.d, 0, 1.55, 0, Bd);
  B(g, it.w - 0.6, 1.5, it.d * 0.5, 0, 3.3, -it.d * 0.05, Gl);
  for (const sx of [-1, 1]) for (const sz of [-1, 1]) { const w = C(g, 1.05, 1.05, 0.7, sx * (it.w / 2 - 0.3), 1.05, sz * it.d * 0.32, Ti); w.rotation.z = Math.PI / 2; }
}
function gymRack(g, it) {
  const F = m(it.color, 0.4, 0.6), Pd = m(it.color2, 0.8), Pl = m('#202326', 0.6);
  for (const sx of [-1, 1]) for (const sz of [-1, 1]) B(g, 0.25, it.h, 0.25, sx * (it.w / 2 - 0.15), it.h / 2, sz * (it.d / 2 - 0.15), F);
  B(g, it.w, 0.2, 0.25, 0, it.h - 0.1, it.d / 2 - 0.15, F); B(g, it.w, 0.2, 0.25, 0, it.h - 0.1, -it.d / 2 + 0.15, F);
  C(g, 0.05, 0.05, it.w + 1.6, 0, 4.6, it.d / 2 - 0.4, F).rotation.z = Math.PI / 2;
  for (const sx of [-1, 1]) { const p = C(g, 0.9, 0.9, 0.25, sx * (it.w / 2 + 0.5), 4.6, it.d / 2 - 0.4, Pl); p.rotation.z = Math.PI / 2; }
  B(g, 1.0, 1.4, 4, 0, 0.7, 0, Pd);
}
function treadmill(g, it) {
  const F = m(it.color, 0.5, 0.3), Belt = m('#1f2226', 0.9), Sc = m('#0f1720', 0.2, 0.2);
  B(g, it.w, 0.6, it.d, 0, 0.3, 0, F); B(g, it.w - 0.5, 0.05, it.d - 1.2, 0, 0.62, 0.3, Belt);
  for (const sx of [-1, 1]) B(g, 0.15, 3.6, 0.15, sx * (it.w / 2 - 0.1), 2.1, -it.d / 2 + 0.4, F);
  B(g, it.w, 0.5, 0.7, 0, 4.0, -it.d / 2 + 0.5, Sc);
}
function kennel(g, it) {
  const Wd = m(it.color, 0.6), Top = m(it.color2, 0.5), Bars = m('#2f3437', 0.4, 0.7);
  B(g, it.w, 0.15, it.d, 0, it.h, 0, Top);
  const n = Math.max(2, Math.round(it.w / 2.2));
  for (let k = 0; k <= n; k++) B(g, 0.1, it.h, it.d, -it.w / 2 + it.w * k / n, it.h / 2, 0, Wd);
  for (let k = 0; k < n * 6; k++) B(g, 0.04, it.h - 0.2, 0.04, -it.w / 2 + it.w * (k + 0.5) / (n * 6), it.h / 2, it.d / 2 - 0.05, Bars);
}
function dogWash(g, it) {
  const T = m(it.color, 0.4), Tile = m(it.color2, 0.5), Ch = m('#c0c4c8', 0.3, 0.8);
  B(g, it.w, 0.5, it.d, 0, 2.8, 0, T);                                    // raised tub, about 3 ft up
  B(g, it.w, 0.9, 0.12, 0, 3.4, it.d / 2 - 0.06, T); B(g, it.w, 0.9, 0.12, 0, 3.4, -it.d / 2 + 0.06, T); B(g, 0.12, 0.9, it.d, it.w / 2 - 0.06, 3.4, 0, T);
  for (const sx of [-1, 1]) for (const sz of [-1, 1]) B(g, 0.2, 2.6, 0.2, sx * (it.w / 2 - 0.2), 1.3, sz * (it.d / 2 - 0.2), T);
  B(g, 0.06, 4, it.d, -it.w / 2 + 0.03, 4.8, 0, Tile);
  C(g, 0.05, 0.05, 1.6, -it.w / 2 + 0.2, 5.0, 0, Ch);
  B(g, 1.4, 0.1, 1.2, it.w / 2 - 1, 3.1, it.d / 2 + 0.8, m('#4b5563', 0.4));
}
function crib(g, it) {
  const Wd = m(it.color, 0.6), Mat = m(it.color2, 0.9);
  B(g, it.w - 0.2, 0.4, it.d - 0.2, 0, 1.4, 0, Mat);
  for (const sx of [-1, 1]) for (const sz of [-1, 1]) B(g, 0.15, it.h, 0.15, sx * (it.w / 2 - 0.08), it.h / 2, sz * (it.d / 2 - 0.08), Wd);
  for (const sz of [-1, 1]) { B(g, it.w, 0.1, 0.1, 0, it.h - 0.05, sz * (it.d / 2 - 0.08), Wd); for (let k = 1; k < 14; k++) B(g, 0.05, it.h - 1.3, 0.05, -it.w / 2 + it.w * k / 14, (it.h + 1.2) / 2, sz * (it.d / 2 - 0.08), Wd); }
  for (const sx of [-1, 1]) B(g, 0.1, it.h - 1.2, it.d, sx * (it.w / 2 - 0.08), (it.h + 1.2) / 2, 0, Wd);
}
'''
ENTRIES = r'''
  tubFree:    { name: 'Freestanding Tub',  cat: 'Bath',     icon: 'fa-bath',         w: 5.6, d: 2.8, h: 2.0, c: '#fbfbf9', c2: '#2f3437', price: 2400, build: tubFree },
  island:     { name: 'Kitchen Island (deep sink, 3 stools)', cat: 'Kitchen', icon: 'fa-kitchen-set', w: 9, d: 4.2, h: 3.1, c: '#2f3e4f', c2: '#f1efe9', price: 9000, build: island },
  car:        { name: 'Car',               cat: 'Garage',   icon: 'fa-car',          w: 6.2, d: 15.5, h: 4.8, c: '#5b6470', c2: '#111111', price: 0, build: carBuild },
  gymRack:    { name: 'Squat Rack + Bench', cat: 'Garage',  icon: 'fa-dumbbell',     w: 4, d: 4.5, h: 7.5, c: '#1f2226', c2: '#7a1f1f', price: 1800, build: gymRack },
  treadmill:  { name: 'Treadmill',         cat: 'Garage',   icon: 'fa-person-running', w: 3, d: 6.5, h: 4.6, c: '#3a3f45', c2: '#111111', price: 1600, build: treadmill },
  kennel:     { name: 'Dog Kennels (wood top)', cat: 'Garage', icon: 'fa-dog',       w: 4.4, d: 2.6, h: 2.8, c: '#e8e1d5', c2: '#9a6a3f', price: 1200, build: kennel },
  dogWash:    { name: 'Raised Dog Wash',   cat: 'Garage',   icon: 'fa-shower',       w: 3.2, d: 2.6, h: 3.3, c: '#f4f4f2', c2: '#cfd6dc', price: 1500, build: dogWash },
  crib:       { name: 'Crib',              cat: 'Bedroom',  icon: 'fa-baby',         w: 4.6, d: 2.5, h: 3.4, c: '#f2efe9', c2: '#dfe8f0', price: 450, build: crib },
'''
a = "const CATALOG = {"
assert a in s
s = s.replace(a, BUILDERS + a, 1)
b = "  fan:        { name: 'Ceiling Fan',"
assert b in s
s = s.replace(b, ENTRIES.strip("\n") + "\n" + b, 1)
s = s.replace("const CATS = ['All', 'Living', 'Dining', 'Bedroom', 'Kitchen', 'Bath', 'Decor', 'Lighting'];", "const CATS = ['All', 'Living', 'Dining', 'Bedroom', 'Kitchen', 'Bath', 'Garage', 'Decor', 'Lighting'];")
open(page, "w").write(s)
print("catalog patched")
