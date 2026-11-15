"""More catalog items for the Obsidian: U-shaped stair (two flights + landing), fireplace with mantel, outdoor grill
station. Idempotent.  Usage: python3 -I add_us_catalog2.py <studio.html>"""
import sys
page = sys.argv[1]; s = open(page).read()
if "/* us-catalog-2 */" in s:
    print("already patched"); sys.exit()
BUILD = r'''/* us-catalog-2 */
function stairU(g, it) {   // two flights side by side and a landing at the far end; rises it.h feet in 18 risers
  const T = m(it.color, 0.55), S = m(it.color2, 0.6), Rl = m('#2f3437', 0.4, 0.6);
  const n = 18, rise = it.h / n, half = it.w / 2 - 0.05, run1 = 9, td = (it.d - half) / run1;
  for (let k = 0; k < run1; k++) { const y = (k + 1) * rise; B(g, half, 0.12, td + 0.05, -it.w / 4, y - 0.06, it.d / 2 - (k + 0.5) * td, T); B(g, half, y - 0.12, 0.08, -it.w / 4, (y - 0.12) / 2, it.d / 2 - k * td - 0.04, S); }
  const ly = run1 * rise; B(g, it.w, 0.2, half, 0, ly - 0.1, -it.d / 2 + half / 2, T);
  for (let k = 0; k < n - run1; k++) { const y = ly + (k + 1) * rise; B(g, half, 0.12, td + 0.05, it.w / 4, y - 0.06, -it.d / 2 + half + (k + 0.5) * td, T); }
  B(g, 0.08, it.h - ly + 3, it.d - half, 0, ly + (it.h - ly) / 2 + 1, half / 2, S);          // centre wall between the flights
  for (const sx of [-1, 1]) B(g, 0.06, 0.08, it.d, sx * (it.w / 2 - 0.05), 3.2 + (sx < 0 ? ly / 2 : ly + (it.h - ly) / 2), 0, Rl);
}
function fireplace(g, it) {
  const St = m(it.color, 0.8), Fb = m('#1b1d20', 0.9), Mt = m(it.color2, 0.5), Fl = m('#ff9a3c', 0.6, 0, { emissive: 0xff7a1a, emissiveIntensity: 0.8 });
  B(g, it.w, it.h, it.d * 0.6, 0, it.h / 2, -it.d * 0.2, St);           // surround up the wall
  B(g, it.w * 0.55, 2.3, 0.1, 0, 1.7, it.d * 0.1 + 0.02, Fb);            // firebox
  B(g, it.w * 0.45, 0.35, 0.05, 0, 1.0, it.d * 0.1 + 0.08, Fl);
  B(g, it.w + 0.4, 0.3, it.d * 0.45, 0, 4.2, it.d * 0.08, Mt);           // mantel
  B(g, it.w + 0.6, 0.3, it.d, 0, 0.15, 0, St);                           // hearth
  if (it.tvAbove !== false) B(g, it.w * 0.8, 2.6, 0.12, 0, 6.1, it.d * 0.1 + 0.08, m('#111316', 0.3, 0.2));   // TV over the mantel
}
function grill(g, it) {
  const Cb = m(it.color, 0.6), Tp = m(it.color2, 0.3), Ss = m('#b9bec4', 0.25, 0.85), Dk = m('#1f2226', 0.5);
  B(g, it.w, 2.8, it.d, 0, 1.4, 0, Cb); B(g, it.w + 0.1, 0.15, it.d + 0.1, 0, 2.9, 0, Tp);
  B(g, 3, 0.5, it.d - 0.4, -it.w * 0.15, 3.2, 0, Ss); B(g, 3, 0.9, 0.1, -it.w * 0.15, 3.5, -it.d / 2 + 0.25, Ss);
  B(g, 2, 2.2, 0.05, it.w * 0.3, 1.3, it.d / 2 + 0.02, Dk);              // outdoor fridge door
}
'''
ENTRIES = r'''
  stairU:     { name: 'Stair (U, to 2nd floor)', cat: 'Living', icon: 'fa-stairs',   w: 8, d: 10.5, h: 11.1, c: '#b08a64', c2: '#f3efe7', price: 0, build: stairU },
  fireplace:  { name: 'Fireplace + Mantel', cat: 'Living',   icon: 'fa-fire',        w: 6, d: 2, h: 9.5, c: '#e9e4dc', c2: '#6b4a2e', price: 9000, build: fireplace },
  grill:      { name: 'Outdoor Kitchen (grill + fridge)', cat: 'Kitchen', icon: 'fa-fire-burner', w: 8, d: 2.6, h: 3.6, c: '#8a8f96', c2: '#d9d4cb', price: 12000, build: grill },
'''
a = "const CATALOG = {"; assert a in s; s = s.replace(a, BUILD + a, 1)
b = "  fan:        { name: 'Ceiling Fan',"; assert b in s; s = s.replace(b, ENTRIES.strip("\n") + "\n" + b, 1)
s = s.replace("const isFlat = it => it.h <= 0.1 || it.type === 'wallPaint'", "const isFlat = it => it.h <= 0.1 || it.type === 'stairU' || it.type === 'wallPaint'", 1)   # a stair spans walls by design
open(page, "w").write(s); print("catalog 2 patched")
