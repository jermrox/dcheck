"""Parse crawled AR Homes plan pages (HTML) into a normalized blueprints.json.

Usage: python3 -I parse_arhomes.py <pages_dir> <out.json>
Only metadata and links are stored (no image/PDF binaries).
"""
import html
import json
import re
import sys
from pathlib import Path

BASE = "https://www.arhomes.com"


def clean_text(t):
    body = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", t, flags=re.S)
    txt = html.unescape(re.sub(r"<[^>]+>", "\n", body))
    return [l.strip() for l in txt.split("\n") if l.strip()]


def parse(path):
    t = Path(path).read_text(encoding="utf8", errors="ignore")
    lines = clean_text(t)
    rec = {"source_file": Path(path).name}
    m = re.search(r'<link rel="canonical" href="([^"]+)"', t)
    rec["url"] = m.group(1) if m else None
    m = re.search(r"<h1[^>]*>(.*?)</h1>", t, flags=re.S)
    rec["name"] = html.unescape(re.sub(r"<[^>]+>", "", m.group(1))).strip() if m else None
    for l in lines:
        if m2 := re.match(r"([\d,]+)\s*SQ FT", l, re.I):
            rec["sqft"] = int(m2.group(1).replace(",", ""))
        for key, field in [("Bedrooms", "bedrooms"), ("Bathrooms", "bathrooms"),
                           ("Half Bath", "half_baths"), ("Stories", "stories"),
                           ("Garages", "garages")]:
            if m2 := re.match(rf"{key}:\s*(\d+)", l):
                rec[field] = int(m2.group(1))
    media = sorted(set(re.findall(r"https://www\.arhomes\.com/wp-content/uploads/[^\"'\s)]+", t)))
    media = [u for u in media if "arhomes-logo" not in u]
    rec["floorplan_pdfs"] = [u for u in media if u.lower().endswith(".pdf")]
    imgs = [u for u in media if re.search(r"\.(webp|jpe?g|png)$", u, re.I)]
    rec["floorplan_images"] = [u for u in imgs if re.search(r"(?i)(_|-)fp|floor.?plan|WebFP", u)]
    rec["photos"] = [u for u in imgs if u not in rec["floorplan_images"]]
    rec["elevations"] = sorted({l for l in lines if re.search(r"(?i)elevation [A-Z]\b", l)})
    rec["tags"] = sorted({c for c in re.findall(r'rel="tag"[^>]*>([^<]+)<', t)})
    return rec


def main():
    pages, out = Path(sys.argv[1]), Path(sys.argv[2])
    recs = [parse(p) for p in sorted(pages.glob("*.html"))]
    out.write_text(json.dumps({"source": BASE, "count": len(recs), "plans": recs}, indent=2))
    print(f"wrote {len(recs)} plans -> {out}")


if __name__ == "__main__":
    main()
