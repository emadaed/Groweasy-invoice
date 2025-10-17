# Security Design Overview

## IAM and Access Control
- Principle of Least Privilege enforced across services.
- OIDC-based GitHub → AWS authentication without static credentials.
- Inline policy added for `cloudformation:GetTemplate`.

## Secrets Management
- Application secrets stored in Elastic Beanstalk environment variables.
- Sensitive files (`eb_env.json`) excluded via `.gitignore`.

## Encryption
- S3 and RDS with AES-256 encryption.
- KMS used for Parameter Store secrets.

