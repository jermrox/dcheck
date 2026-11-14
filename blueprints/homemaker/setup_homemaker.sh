#!/usr/bin/env bash
# Put every traced AR Homes blueprint into HOMEMAKER (https://github.com/bayllama/homemaker, MIT) as its own project.
# Usage: ./setup_homemaker.sh <models.json> <blueprint_images_dir> [homemaker_dir]
#   models.json            from blueprints/model/bundle_models.py (+ apply_reviews.py)
#   blueprint_images_dir   the downloaded floor-plan images (<base>.jpg / .webp)
# Then: cd <homemaker_dir>/homemaker && npm start   -> http://localhost:3000
set -euo pipefail
MODELS="${1:?models.json}"; FP="${2:?blueprint images dir}"; HM="${3:-$HOME/homemaker}"
HERE="$(cd "$(dirname "$0")" && pwd)"
[ -d "$HM/.git" ] || git clone --depth 1 https://github.com/bayllama/homemaker "$HM"
# HOMEMAKER's file watcher crashes if project folders change under it: stop a running server first
pkill -f "node server.js" 2>/dev/null || true
(cd "$HM/homemaker" && [ -d node_modules/ws ] || npm install --no-audit --no-fund)
python3 -c "import cv2, numpy" 2>/dev/null || pip install --quiet opencv-python-headless numpy
python3 -I "$HERE/to_homemaker.py" "$MODELS" "$FP" "$HM/homemaker/projects"
echo "Done. Start it with:  cd $HM/homemaker && npm start   (projects are named ar-<plan>)"
