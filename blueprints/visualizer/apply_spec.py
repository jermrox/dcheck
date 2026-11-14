"""Apply a builder specification (finishes per room) to Interior Design Visualizer homes.

Usage: python3 -I apply_spec.py <spec.json> <out_dir> <home.json> [...]
spec.json: {"wall": "#hex", "rules": [[room-name regex, floor key, note], ...], "house": "...", "source": "..."}
Floor keys must exist in the visualizer (oak, carpet, concrete, bathtile, greytile, ...; carpet and concrete were
added to the local copy). The first rule that matches a room name wins. Writes a design (finishes + empty item list,
so the visualizer still auto-furnishes) and appends the matched notes to the plan subtitle file as spec notes.
"""
import json, os, re, sys
spec_path, out, *homes = sys.argv[1:]
spec = json.load(open(spec_path)); os.makedirs(out, exist_ok=True)
for h in homes:
    home = json.load(open(h)); plan = home["plan"]; fin, notes, unmatched = {}, [], []
    for r in plan["rooms"]:
        rule = next((q for q in spec["rules"] if re.search(q[0], r["name"])), None)
        if rule:
            fin[r["id"]] = {"wall": spec.get("wall", "#f1ede6"), "floor": rule[1]}; notes.append(f"{r['name']}: {rule[2]}")
        else: unmatched.append(r["name"])
    home["design"] = {"v": 4, "vastu": {"facing": plan.get("facing", "N"), "overlay": False}, "lighting": "day",
                      "finishes": fin, "items": []}
    plan["specNotes"] = {"source": spec.get("source"), "house": spec.get("house"), "rooms": notes}
    fn = os.path.join(out, os.path.basename(h).replace(".home.json", "-spec.home.json"))
    json.dump(home, open(fn, "w"), separators=(",", ":"))
    print(f"{os.path.basename(fn)}: {len(fin)} rooms finished per spec; unmatched: {unmatched or 'none'}")
