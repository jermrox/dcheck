"""Add the "Site" layer (lot, terrain, roof, other floor) to an Interior Studio page.

Usage: python3 -I add_site_layer.py <interactive_interior_visualizer.html> <lot2-site-data.js>
  Patches the page in place (idempotent): a Site button in the 3D toolbar, a larger orbit range while the
  site is on, and site_layer.js inlined. Copies the site data (from build_lot_scene.py's third argument)
  to obsidian/lot2-site-data.js next to the page. Open the page with ?site=1 to start with the site on.
"""
import os, re, shutil, sys

page, data = sys.argv[1], sys.argv[2]
s = open(page).read()
here = os.path.dirname(os.path.abspath(__file__))
layer = open(os.path.join(here, "site_layer.js")).read()
BTN = ('<button id="tb-site" class="icon-btn" onclick="toggleSite()" title="Site: lot, terrain, roof and the other floor">'
       '<i class="fa-solid fa-mountain-sun"></i></button>')
anchor = '<button id="tb-labels"'
if 'id="tb-site"' not in s:
    assert anchor in s; s = s.replace(anchor, BTN + "\n        " + anchor, 1)
clamp = "Math.min(110, orbitGoal.dist * f)"
if clamp in s: s = s.replace(clamp, "Math.min(window.__maxDist || 110, orbitGoal.dist * f)")
s = re.sub(r"<script id=\"site-layer\">.*?</script>\n", "", s, flags=re.S)
i = s.rindex("</body>")
s = s[:i] + '<script id="site-layer">' + layer + "</script>\n" + s[i:]
open(page, "w").write(s)
dst = os.path.join(os.path.dirname(os.path.abspath(page)), "obsidian", "lot2-site-data.js")
os.makedirs(os.path.dirname(dst), exist_ok=True); shutil.copyfile(data, dst)
print(f"{page}: site layer added; data -> {dst}")
