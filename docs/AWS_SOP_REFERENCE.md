# AWS SOP Reference

## Infrastructure SOPs
- **Region Alignment:** All resources deployed to `us-east-2`.
- **Naming Convention:** groweasy-<service>-<purpose>.
- **Deployment Policy:** CI/CD automation via GitHub Actions.

## IAM SOPs
- Roles must include least privilege actions.
- Every Elastic Beanstalk environment requires CloudFormation read permission.

