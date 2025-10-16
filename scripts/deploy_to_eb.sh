#!/usr/bin/env bash
set -euo pipefail
# Helper: create app version and update EB environment
# Usage: ./scripts/deploy_to_eb.sh <s3-bucket> <artifact-key> <version-label>

S3_BUCKET=${1:-${S3_BUCKET:-}}
ARTIFACT_KEY=${2:-}
VERSION_LABEL=${3:-"v$(date -u +%Y%m%dT%H%M%SZ)"}
APP_NAME=${4:-${APP_NAME:-groweasy-invoice-app}}
EB_ENV_NAME=${5:-${EB_ENV_NAME:-Groweasy-invoice-app-env}}
AWS_REGION=${6:-${AWS_REGION:-us-east-2}}

if [ -z "$S3_BUCKET" ] || [ -z "$ARTIFACT_KEY" ]; then
  echo "Usage: $0 <s3-bucket> <artifact-key> [version-label] [app-name] [env-name] [region]"
  exit 2
fi

echo "Creating application version $VERSION_LABEL from s3://$S3_BUCKET/$ARTIFACT_KEY"
aws elasticbeanstalk create-application-version       --application-name "$APP_NAME"       --version-label "$VERSION_LABEL"       --source-bundle S3Bucket="$S3_BUCKET",S3Key="$ARTIFACT_KEY"       --region "$AWS_REGION"

echo "Updating environment $EB_ENV_NAME -> version $VERSION_LABEL"
aws elasticbeanstalk update-environment       --environment-name "$EB_ENV_NAME"       --version-label "$VERSION_LABEL"       --region "$AWS_REGION"
