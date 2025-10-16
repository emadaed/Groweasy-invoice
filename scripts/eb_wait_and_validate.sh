#!/usr/bin/env bash
set -euo pipefail
# Poll Elastic Beanstalk environment until Health is Ok or Timeout
EB_ENV_NAME=${EB_ENV_NAME:-${1:-Groweasy-invoice-app-env}}
AWS_REGION=${AWS_REGION:-us-east-2}
TIMEOUT_MINUTES=${TIMEOUT_MINUTES:-15}

echo "Waiting for Elastic Beanstalk environment '$EB_ENV_NAME' to report status 'Ready/Ok' (timeout ${TIMEOUT_MINUTES}m)"
SECONDS=0
TIMEOUT=$(( TIMEOUT_MINUTES * 60 ))
while [ $SECONDS -lt $TIMEOUT ]; do
  RESP=$(aws elasticbeanstalk describe-environments --environment-names "$EB_ENV_NAME" --region "$AWS_REGION" --output json)
  STATUS=$(echo "$RESP" | jq -r '.Environments[0].Status // empty')
  HEALTH=$(echo "$RESP" | jq -r '.Environments[0].Health // empty')
  echo "Status=$STATUS Health=$HEALTH"
  if [ "$STATUS" = "Ready" ] && ([ "$HEALTH" = "Ok" ] || [ "$HEALTH" = "Green" ]); then
    echo "Environment is Ready/Ok"
    exit 0
  fi
  if [ "$STATUS" = "Terminated" ] || [ "$STATUS" = "Terminating" ]; then
    echo "Environment in terminated state. Exiting."
    exit 2
  fi
  sleep 10
done
echo "Timeout waiting for environment to become healthy. Last known status: Status=$STATUS Health=$HEALTH"
exit 3
