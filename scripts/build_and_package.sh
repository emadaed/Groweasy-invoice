#!/usr/bin/env bash
set -e  # Exit immediately on error
set -o pipefail

echo "──────────────────────────────────────────────"
echo "🚀 Starting AWS build and package process..."
echo "──────────────────────────────────────────────"

# === CONFIG ===
APP_NAME="${APP_NAME:-groweasy-invoice-app}"
BUILD_DIR="dist"
TIMESTAMP=$(date +'%Y%m%d%H%M%S')
ZIP_NAME="${APP_NAME}-build-${TIMESTAMP}.zip"
S3_BUCKET="${S3_BUCKET:?S3_BUCKET not set}"
AWS_REGION="${AWS_REGION:?AWS_REGION not set}"

# === PREPARE DIST DIRECTORY ===
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR"

# === COLLECT FILES ===
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

# === VERIFY UPLOAD ===
echo "🔍 Verifying upload..."
if aws s3 ls "s3://$S3_BUCKET/$ZIP_NAME" --region "$AWS_REGION" > /dev/null; then
  echo "✅ Upload complete and verified."
else
  echo "❌ Upload verification failed. Artifact not found in S3."
  exit 1
fi

# === WRITE ARTIFACT KEY ===
ARTIFACT_KEY="$ZIP_NAME"
echo "$ARTIFACT_KEY" > "$BUILD_DIR/artifact_key.txt"
echo "✅ Artifact key written to $BUILD_DIR/artifact_key.txt"

# === FINAL SUMMARY ===
echo "──────────────────────────────────────────────"
echo "🎯 Build and package stage completed successfully."
echo "📦 Artifact: $ARTIFACT_KEY"
echo "☁️ S3 Location: s3://$S3_BUCKET/$ARTIFACT_KEY"
echo "──────────────────────────────────────────────"
