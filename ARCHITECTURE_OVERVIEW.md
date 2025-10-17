# System Architecture Overview

## 1. Overview
GrowEasy Invoice is built on AWS Elastic Beanstalk with modular architecture for high scalability and security.

## 2. Core Components
| Layer | Technology | Description |
|-------|-------------|-------------|
| Backend | Flask (Python) | REST API + business logic |
| Frontend | HTML, TailwindCSS | Responsive UI |
| Database | PostgreSQL (AWS RDS) | Relational data layer |
| Storage | AWS S3 | Artifact + media storage |
| Hosting | AWS Elastic Beanstalk | Application runtime |
| CI/CD | GitHub Actions | Automated build & deployment |
| Monitoring | CloudWatch + EB Health | Observability |

## 3. Architecture Diagram
_A diagram should be added here showing request flow from client → EB → RDS → S3._

## 4. Security Layers
- IAM roles (OIDC connected)
- KMS encryption for secrets
- HTTPS-ready configuration

## 5. Scalability
- Auto-scaling groups managed by Elastic Beanstalk
- Stateless app design using environment variables
