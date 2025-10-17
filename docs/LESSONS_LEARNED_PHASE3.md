# Lessons Learned — Phase 3

## Technical Takeaways
- Always align S3 and EB regions before deployment.
- Persist GitHub Action environment variables explicitly using `$GITHUB_ENV`.
- Ensure CloudFormation permissions for EB automation.

## Process Improvements
- Standardize IAM role creation scripts.
- Keep EB environment variables separate from repo files.
- Validate artifact presence in S3 before version creation.

