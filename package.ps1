# Windows helper to run packaging and upload (PowerShell)
param(
  [string]$S3Bucket = $env:S3_BUCKET,
  [string]$Region = $env:AWS_REGION
)

if (-not $S3Bucket) {
  Write-Error "S3_BUCKET not provided. Set env or pass param."
  exit 1
}

Write-Host "Running build_and_package.sh via bash..."
bash -lc "./scripts/build_and_package.sh"

$key = (cat dist/artifact_key.txt)
Write-Host "Artifact key: $key"
Write-Host "To deploy, use deploy helper or commit & push to trigger GitHub Actions."
