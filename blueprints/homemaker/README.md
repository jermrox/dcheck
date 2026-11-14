# AR Homes blueprints in HOMEMAKER

[HOMEMAKER](https://github.com/bayllama/homemaker) (MIT, by bayllama) is a browser 3D home designer: a floor-plan
editor that turns traced walls into a first-person walkthrough, plus a Claude chat agent that adds doors, windows,
ceilings, furniture and textures by editing the project's code. This folder exports our traced AR Homes blueprints
into it, so each plan can be walked through and refined there.

`to_homemaker.py` writes one project per blueprint sheet, `projects/ar-<plan>/`:

| File | Contents |
|---|---|
| `project.json` / `walls.json` | traced walls as centre lines in metres (thickness from the drawing, 9 ft high), scale in px per metre, camera, lighting |
| `floorplan.png` | the blueprint; HOMEMAKER maps image px to metres as px / pixelsPerMeter, so walls sit exactly on the drawing |
| `rooms/openings.js` | door headers, window sills, headers and glass at real heights |
| `CLAUDE.md` | scale grade, reviewer results and known gaps, read by HOMEMAKER's agent before it edits |

## Run it

```bash
./setup_homemaker.sh <models.json> <blueprint_images_dir> [~/homemaker]
cd ~/homemaker/homemaker && npm start        # http://localhost:3000, open a project named ar-<plan>
```

The walkthrough and floor-plan editor work without a key. HOMEMAKER's chat agent needs your Anthropic API key,
entered in its page; it is held in that server's memory only.

## Refining a plan toward 1:1

1. **Edit Floor Plan**: walls show over the blueprint. Add missed walls (glass walls and sliders are the usual gaps),
   delete false ones (stairs, counters, columns), then **Convert to 3D**.
2. **Scale**: set one wall to its printed length; HOMEMAKER rescales the plan from it. Plans graded ESTIMATED or
   NEEDS CHECKING in `CLAUDE.md` need this most.
3. **Chat agent**: ask it to add the real doors, windows and ceilings shown on `floorplan.png`.

Limits: levels shown side by side on a sheet are all placed at ground level; on sheets drawn with different scales
per level, only one scale is used. AR Homes states its plan dimensions are approximate, and its drawings are
copyrighted: keep the generated projects private. They are not committed to this repo.
