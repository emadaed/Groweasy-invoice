# GrowEasy-Invoice — Phase 3 CI/CD Automation Plan

## Overview
This document describes the AWS-native CI/CD automation implemented for GrowEasy-Invoice.

## Objectives
- Continuous Deployment to AWS Elastic Beanstalk
- Versioned build artifacts via S3
- Secure OIDC-based authentication (no AWS keys)

## Pipeline Workflow
1. Lint and build Flask app.
2. Package artifact and upload to S3.
3. Create Elastic Beanstalk application version.
4. Deploy to the configured environment.
5. Validate health via AWS CLI.

## Files & Scripts
| Path | Purpose |
|------|----------|
| `.github/workflows/ci_cd.yml` | Main GitHub Actions pipeline |
| `scripts/build_and_package.sh` | Builds Docker/Flask artifact |
| `scripts/deploy_to_eb.sh` | Triggers AWS EB deployment |
| `scripts/eb_wait_and_validate.sh` | Waits for green health state |
| `config/eb-env.json.template` | Template for environment configuration |

## Environment Variables (Secrets)
| Name | Description |
|------|--------------|
| `AWS_ROLE_TO_ASSUME` | IAM Role for OIDC |
| `AWS_REGION` | AWS region |
| `S3_BUCKET` | Artifact bucket |
| `APP_NAME` | Elastic Beanstalk application |
| `EB_ENV_NAME` | EB environment name |

## Future Enhancements
- Blue/Green deployment support
- Rollback automation
- Slack notifications for deploy status
