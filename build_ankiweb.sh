#!/bin/sh
# Build a zip suitable for uploading to AnkiWeb (Tools > Add-ons > Install from file).
# AnkiWeb expects the contents of the addon folder zipped directly (not the folder itself).
set -e

NAME="adjust_review_times"
OUT="dist/${NAME}.ankiaddon"

mkdir -p dist
rm -f "$OUT"

cd addon
zip -r "../$OUT" . --exclude "*.pyc" --exclude "__pycache__/*" --exclude ".DS_Store" --exclude "backups/*" --exclude "*.log" --exclude "*.anki2" --exclude "meta.json" --exclude "manifest.json"
cd ..

echo "Built: $OUT"
