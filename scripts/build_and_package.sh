#!/usr/bin/env bash
# Phase 3.9 Full ZIP Builder
# File: build_and_package.sh
# Usage: From repository root: chmod +x build_and_package.sh && ./build_and_package.sh
# This script prepares a production-ready ZIP for GrowEasy-Invoice Phase 3.9
# It bundles the Flask app, templates, static assets (including QR and logo),
# EB config files, Procfile, requirements.txt, and produces:
#   ./dist/groweasy-invoice-phase3.9-<timestamp>.zip
#   ./dist/groweasy-invoice-phase3.9-<timestamp>.zip.b64  (Base64-safe wrapper for transports)
# It depends on Python 3.9+ available as `python3` and `pip` available.
# It will call the helper Python scripts included below.

set -euo pipefail
IFS=$'\n\t'

REPO_ROOT="$(pwd)"
BUILD_DIR="$REPO_ROOT/.build_phase3_9"
DIST_DIR="$REPO_ROOT/dist"
TIMESTAMP=$(date +%Y%m%d%H%M%S)
ZIPNAME="groweasy-invoice-phase3.9-$TIMESTAMP.zip"
ZIPPATH="$DIST_DIR/$ZIPNAME"
B64PATH="$ZIPPATH.b64"

# Files / directories to include (relative to repo root)
INCLUDE=(
  "app.py"               # main Flask entry (rename as needed)
  "wsgi.py"             # wsgi/gunicorn entry
  "requirements.txt"
  "Procfile"
  "runtime.txt"
  "templates/"
  "static/"
  "assets/qr/"
  ".ebextensions/"
  ".platform/"
  "README.md"
  "LICENSE"
)

# Allow override by environment variable (e.g. INCLUDE_EXTRA="migrations/ db/...")
if [[ -n "${INCLUDE_EXTRA:-}" ]]; then
  for p in $INCLUDE_EXTRA; do
    INCLUDE+=("$p")
  done
fi

echo "[build] Repo root: $REPO_ROOT"
echo "[build] Cleaning previous build dirs"
rm -rf "$BUILD_DIR" "$DIST_DIR"
mkdir -p "$BUILD_DIR" "$DIST_DIR"

# Verify required files exist and copy
missing=()
for p in "${INCLUDE[@]}"; do
  if [[ -e "$REPO_ROOT/$p" ]]; then
    echo "[build] Adding: $p"
    # Preserve structure
    mkdir -p "$BUILD_DIR/$(dirname "$p")"
    if [[ -d "$REPO_ROOT/$p" ]]; then
      cp -a "$REPO_ROOT/$p" "$BUILD_DIR/$(dirname "$p")/"
    else
      cp -a "$REPO_ROOT/$p" "$BUILD_DIR/$p"
    fi
  else
    missing+=("$p")
  fi
done

if [[ ${#missing[@]} -gt 0 ]]; then
  echo "\n[warning] The following expected files/directories were missing and NOT included:" >&2
  for m in "${missing[@]}"; do echo "  - $m" >&2; done
  echo "If these are intentional (e.g. different filenames), set INCLUDE_EXTRA or update the script." >&2
fi

# Ensure QR assets exist; if not, create placeholder via helper
if [[ ! -d "$BUILD_DIR/assets/qr" || -z "$(ls -A "$BUILD_DIR/assets/qr" 2>/dev/null || true)" ]]; then
  echo "[build] QR assets missing — generating placeholder assets"
  mkdir -p "$BUILD_DIR/assets/qr"
  python3 - <<'PY'
from pathlib import Path
from PIL import Image, ImageDraw
p=Path('.build_phase3_9/assets/qr/placeholder-logo.png')
im=Image.new('RGBA',(400,400),(255,255,255,0))
d=ImageDraw.Draw(im)
d.rectangle([50,50,350,350],outline=(30,120,180,255),width=6)
d.text((120,180),'GrowEasy',fill=(30,120,180,255))
im.save(p)
print('placeholder written:',p)
PY
fi

# Optionally generate QR PNGs using qr_generate.py helper if present in repo root; otherwise skip
if [[ -f "$REPO_ROOT/tools/qr_generate.py" ]]; then
  echo "[build] Running tools/qr_generate.py to produce QR assets"
  python3 "$REPO_ROOT/tools/qr_generate.py" --outdir "$BUILD_DIR/assets/qr"
else
  echo "[build] No tools/qr_generate.py helper found — skipping QR regeneration (use tools/qr_generate.py to generate)"
fi

# Create a requirements vendor directory (optional) - we will not vendor packages by default to keep ZIP small
# But we will freeze the exact requirements.txt into build for reproducible deploy
if [[ -f "$REPO_ROOT/requirements.txt" ]]; then
  cp "$REPO_ROOT/requirements.txt" "$BUILD_DIR/requirements.txt"
fi

# Remove any local dev files not needed
find "$BUILD_DIR" -name '*.pyc' -delete

# Write a small manifest for traceability
cat > "$BUILD_DIR/.phase3_9_manifest.txt" <<EOF
GrowEasy-Invoice Phase 3.9 ZIP
timestamp: $TIMESTAMP
zip: $ZIPNAME
included:
$(for p in "${INCLUDE[@]}"; do echo " - $p"; done)
EOF

# Create zip
pushd "$BUILD_DIR" >/dev/null
zip -r9 "$ZIPPATH" . >/dev/null
popd >/dev/null

echo "[build] ZIP created: $ZIPPATH"

# Create a Base64-safe wrapper: gzip the zip and base64 encode so it's safe to paste or transport
python3 - <<PY
import base64,sys,gzip
from pathlib import Path
zip_path=Path(r"$ZIPPATH")
out=Path(r"$B64PATH")
with open(zip_path,'rb') as f:
    content=f.read()
# gzip-compress to reduce size for base64 transport
comp=gzip.compress(content)
with open(out,'wb') as f:
    f.write(base64.b64encode(comp))
print('wrote base64 gzip file:',out)
PY

# Quick integrity check
if command -v unzip >/dev/null 2>&1; then
  echo "[build] Verifying zip integrity (list):"
  unzip -l "$ZIPPATH" | sed -n '1,20p'
fi

cat > "$DIST_DIR/README_DIST.txt" <<EOF
GrowEasy-Invoice Phase 3.9 packaged distribution
ZIP: $ZIPNAME
Generated: $TIMESTAMP
How to use:
  - Download and unzip: unzip $ZIPNAME
  - Deploy to Elastic Beanstalk or Render according to your CI/CD pipeline
  - If you need to re-create this ZIP on another machine, run the included build_and_package.sh at repo root
EOF

echo "[build] Distribution prepared: $ZIPPATH and $B64PATH"

echo "[build] Done."

# ---------------------------
# Helper: tools/qr_generate.py
# ---------------------------
# Below is a recommended Python helper to generate branded QR codes with an embedded logo.
# Save as tools/qr_generate.py in your repo if you want to use it. The builder will call it.
cat > tools/qr_generate.py <<'PY'
#!/usr/bin/env python3
"""
Generate high-quality QR codes (PNG + SVG) with an embedded center-logo.
Requirements: qrcode[pil], pillow
Usage: python3 tools/qr_generate.py --data 'https://example.com/invoice/INV-123' --outdir ./assets/qr --logo ./assets/logo.png
"""
import argparse
from pathlib import Path
import qrcode
from PIL import Image

parser=argparse.ArgumentParser()
parser.add_argument('--data',default='https://groweasy.example/invoice/INV-000',help='Data to encode')
parser.add_argument('--outdir',default='./assets/qr',help='Output directory')
parser.add_argument('--logo',default='./assets/logo.png',help='Logo to embed (optional)')
parser.add_argument('--size',type=int,default=800,help='Pixel size of final QR PNG')
args=parser.parse_args()

outdir=Path(args.outdir)
outdir.mkdir(parents=True,exist_ok=True)
qr=qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_H,box_size=10,border=4)
qr.add_data(args.data)
qr.make(fit=True)
im=qr.make_image(fill_color="black", back_color="white").convert('RGBA')
im=im.resize((args.size,args.size))

logo=Path(args.logo)
if logo.exists():
    logo_im=Image.open(logo).convert('RGBA')
    # scale logo to 20% of QR width
    w=int(args.size*0.20)
    logo_im=logo_im.resize((w,w))
    pos=((args.size-w)//2,(args.size-w)//2)
    im.paste(logo_im,pos,logo_im)

png_out=outdir/('qr_'+str(args.size)+'.png')
im.save(png_out)
print('wrote',png_out)
PY

# ---------------------------
# Helper: tools/base64_zip_rebuilder.py
# ---------------------------
# Save as tools/base64_zip_rebuilder.py — decodes the .b64 gzip wrapper and restores the zip
cat > tools/base64_zip_rebuilder.py <<'PY'
#!/usr/bin/env python3
"""
Rebuild original zip from the base64-gzip wrapper produced by build_and_package.sh
Usage: python3 tools/base64_zip_rebuilder.py input.b64 output.zip
"""
import sys,base64,gzip
from pathlib import Path
if len(sys.argv)<3:
    print('usage: base64_zip_rebuilder.py input.b64 output.zip')
    sys.exit(2)
inp=Path(sys.argv[1])
outp=Path(sys.argv[2])
data=base64.b64decode(inp.read_bytes())
content=gzip.decompress(data)
outp.write_bytes(content)
print('wrote',outp)
PY

# Make helpers executable
chmod +x tools/qr_generate.py tools/base64_zip_rebuilder.py || true

# End of code file
