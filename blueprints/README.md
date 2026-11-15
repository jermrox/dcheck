# AR Homes blueprint collection

Phase 1 of: collect AR Homes (AR Homes by Arthur Rutenberg, arhomes.com) floor
plans + metadata, to later model them as 3D houses for AR/VR.

- `arhomes_plan_urls.txt` – 309 plan pages from `plan-sitemap.xml` (275) and
  `ls-plan-sitemap.xml` (34, Luxury Simplified).
- `crawl_arhomes.sh` – resumable crawler using the Bright Data CLI (`bdata`),
  honoring robots.txt `Crawl-delay: 10`.
- `parse_arhomes.py` – turns crawled HTML into `blueprints.json`
  (name, sq ft, beds, baths, half baths, stories, garages, elevations,
  floor-plan PDF/image URLs, photos).

Notes: AR Homes states all floor plans/designs are copyrighted. This repo
stores links and metadata only, for internal use; check their terms before
redistributing plan artwork.

## Other leads (GitHub / datasets)
CubiCasa5k, MSD (Modified Swiss Dwellings), MLStructFP, DeepFloorPlan_Pytorch
(includes a floor-plan -> 3D mesh script) – useful for the later 3D modeling step.

## Viewer (prototype)
`viewer/index.html` loads `blueprints.json` and builds a 3D massing model per plan
(footprint from sq ft / stories, windows, garage wing, hip roof) next to the real
floor-plan image, with WebXR AR/VR buttons (three.js). Serve the `blueprints/`
folder over HTTPS (WebXR requires it) e.g. `python3 -m http.server` for local dev.

Limitations: massing only – room layout is not yet derived from the floor plan.
Some Luxury Simplified plans have no `Garages:` field, so garages shows 0 there.
Next step: vectorize floor-plan images/PDFs (see CubiCasa5k / DeepFloorPlan) to
extrude real walls and rooms.
