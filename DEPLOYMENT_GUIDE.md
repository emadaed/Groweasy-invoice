# Deployment Guide

## 1. Prerequisites
- AWS account with Elastic Beanstalk, RDS, and S3 access
- GitHub repository with OIDC role configured
- AWS CLI and EB CLI installed locally

## 2. Environment Setup
```bash
aws configure
# Region: us-east-2
# Output format: json
```

## 3. Deployment Pipeline
- GitHub Actions builds and packages artifacts
- Artifacts uploaded to S3 (`groweasy-invoice-artifacts-us-east-2`)
- EB Application Version auto-created
- Environment updated automatically

## 4. Manual Deployment (Optional)
```bash
eb deploy
```

## 5. Validation
Check status in Elastic Beanstalk Console → Environment Health → **Green**

## 6. Rollback
Use previous version label in:
```bash
aws elasticbeanstalk update-environment --environment-name Groweasy-invoice-app-env --version-label <old-version>
```

