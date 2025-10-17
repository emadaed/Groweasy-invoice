# CI/CD Pipeline Map

## Overview
GitHub Actions automates the build, packaging, and deployment process.

## Stages
1. **Build & Package** — Creates ZIP artifact
2. **Upload to S3** — Uploads artifact to `groweasy-invoice-artifacts-us-east-2`
3. **Create EB Application Version** — Registers version with Elastic Beanstalk
4. **Deploy to Environment** — Updates EB environment automatically
5. **Validate Deployment** — Confirms environment health is green

