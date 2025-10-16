#!/usr/bin/env bash
set -euo pipefail
# Build & package for Elastic Beanstalk (source bundle)
# Expects: S3_BUCKET, AWS_REGION, APP_NAME (env or secrets)
echo ">> Build & package starting"

ROOT_DIR=$(pwd)
DIST_DIR="$ROOT_DIR/dist"
TIMESTAMP=$(date -u +"%Y%m%dT%H%M%SZ")
VERSION_LABEL="v${GITHUB_RUN_NUMBER:-local}-${GITHUB_SHA:-local}"
ARTIFACT_NAME="${APP_NAME:-groweasy-invoice-app}_${TIMESTAMP}.zip"

rm -rf "$DIST_DIR"
mkdir -p "$DIST_DIR/package"
echo "Copying source files..."
rsync -av --exclude='.git' --exclude='dist' --exclude='venv' --exclude='.env' --exclude='*.sqlite3' ./ "$DIST_DIR/package/"

# Ensure Procfile or start command present
if [ ! -f "$DIST_DIR/package/Procfile" ]; then
  echo "web: gunicorn digireceipt_app.wsgi:application --bind 0.0.0.0:$PORT" > "$DIST_DIR/package/Procfile"
  echo "Added default Procfile"
fi

# Create zip
pushd "$DIST_DIR/package" >/dev/null
zip -r "../$ARTIFACT_NAME" . >/dev/null
popd >/dev/null

# Upload to S3
ARTIFACT_PATH="$DIST_DIR/$ARTIFACT_NAME"
if [ -z "${S3_BUCKET:-}" ]; then
  echo "S3_BUCKET not set. Write artifact key to dist/artifact_key.txt and skip upload."
  echo "$ARTIFACT_NAME" > "$DIST_DIR/artifact_key.txt"
else
  ARTIFACT_KEY="artifacts/${ARTIFACT_NAME}"
  echo "Uploading $ARTIFACT_PATH -> s3://$S3_BUCKET/$ARTIFACT_KEY"
  aws s3 cp "$ARTIFACT_PATH" "s3://$S3_BUCKET/$ARTIFACT_KEY" --region "${AWS_REGION:-us-east-2}"
  echo "$ARTIFACT_KEY" > "$DIST_DIR/artifact_key.txt"
fi

echo ">> Package complete. Artifact key written to dist/artifact_key.txt"
