# GrowEasy Invoice

GrowEasy Invoice is a cloud-native invoicing platform designed to simplify billing, record-keeping, and financial transparency for small and medium businesses.

## 🚀 Overview
- **Backend:** Python (Flask)
- **Frontend:** HTML + TailwindCSS
- **Database:** Amazon RDS (PostgreSQL)
- **Hosting:** AWS Elastic Beanstalk
- **Storage:** Amazon S3
- **CI/CD:** GitHub Actions → AWS OIDC
- **Monitoring:** AWS CloudWatch + EB Health

## 📂 Repository Structure
```
Groweasy-invoice/
│
├── app/                  # Flask application code
├── config/               # Environment configuration
├── static/               # Frontend assets
├── templates/            # Jinja templates
├── scripts/              # Deployment and helper scripts
├── docs/                 # Engineering & investor documentation
└── .github/workflows/    # CI/CD pipelines
```

## 📘 Key Documentation
| File | Description |
|------|--------------|
| [ARCHITECTURE_OVERVIEW.md](ARCHITECTURE_OVERVIEW.md) | Full system architecture |
| [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) | AWS deployment instructions |
| [docs/PHASE3_ENGINEERING_REPORT.md](docs/PHASE3_ENGINEERING_REPORT.md) | Phase 3 CI/CD report |
| [docs/LESSONS_LEARNED_PHASE3.md](docs/LESSONS_LEARNED_PHASE3.md) | Lessons & improvements |
| [docs/ROADMAP.md](docs/ROADMAP.md) | Project roadmap |

## 🌐 Live Environment
- **Production:** [Elastic Beanstalk URL](http://your-env.elasticbeanstalk.com)

## 📜 License
Licensed under the MIT License. See [LICENSE](LICENSE) for details.
