#!/usr/bin/env bash
set -e  # Exit immediately on error
set -o pipefail

echo "──────────────────────────────────────────────"
echo "🚀 Starting AWS build and package process..."
echo "──────────────────────────────────────────────"

# === CONFIG ===
APP_NAME="${APP_NAME:-groweasy-invoice-app}"
BUILD_DIR="dist"
ZIP_NAME="${APP_NAME}-build-$(date +'%Y%m%d%H%M%S').zip"
S3_BUCKET="${S3_BUCKET:?S3_BUCKET not set}"
AWS_REGION="${AWS_REGION:?AWS_REGION not set}"

# === PREPARE DIST DIRECTORY ===
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR"

# === DEFINE FILES TO INCLUDE ===
# Adjust these paths if your structure changes
echo "📦 Collecting app files..."
zip -r9 "$BUILD_DIR/$ZIP_NAME" \
  app/ \
  templates/ \
  static/ \
  config/ \
  requirements.txt \
  app.py \
  config.py \
  Dockerfile \
  docker-compose.yml \
  .env.template \
  -x "*.pyc" -x "__pycache__/*" -x "*.git*" > /dev/null

echo "✅ Build artifact created: $BUILD_DIR/$ZIP_NAME"

# === UPLOAD TO S3 ===
echo "☁️ Uploading artifact to S3: s3://$S3_BUCKET/$ZIP_NAME"
aws s3 cp "$BUILD_DIR/$ZIP_NAME" "s3://$S3_BUCKET/$ZIP_NAME" --region "$AWS_REGION"

echo "✅ Upload complete."

# === RECORD ARTIFACT PATH ===
ARTIFACT_KEY="$ZIP_NAME"
echo "$ARTIFACT_KEY" > "$BUILD_DIR/artifact_key.txt"

echo "✅ Artifact key written to $BUILD_DIR/artifact_key.txt"
echo "──────────────────────────────────────────────"
echo "🎯 Build and package stage completed successfully."
echo "──────────────────────────────────────────────"
