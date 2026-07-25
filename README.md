# Internal Developer Platform API

[![Python](https://img.shields.io/badge/Python-3.9+-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Kubernetes](https://img.shields.io/badge/Kubernetes-1.24+-326CE5?style=flat-square&logo=kubernetes&logoColor=white)](https://kubernetes.io/)
[![Terraform](https://img.shields.io/badge/Terraform-1.0+-844FBA?style=flat-square&logo=terraform&logoColor=white)](https://www.terraform.io/)
[![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)](LICENSE)

> A self-service cloud infrastructure and application deployment platform that empowers developers to provision resources and deploy applications without deep DevOps expertise.

---

## Table of Contents

- [Overview](#overview)
- [Live Deployment](#live-deployment)
- [Quick Start](#quick-start)
- [Prerequisites](#prerequisites)
- [Features](#features)
- [Architecture](#architecture)
- [Project Structure](#project-structure)
- [API Endpoints](#api-endpoints)
- [Local Development](#local-development)
- [Terraform](#terraform)
- [Helm Deployment](#helm-deployment)
- [Security](#security)
- [Observability](#observability)
- [CI/CD](#cicd)
- [Implementation Phases](#implementation-phases)
- [Scaling Recommendations](#scaling-recommendations)
- [Contributing](#contributing)
- [License](#license)

---

## Overview

The **Internal Developer Platform (IDP) API** is a FastAPI-based platform that enables self-service cloud infrastructure provisioning and application deployments. It abstracts the complexity of Kubernetes and Terraform, allowing developers to deploy containerized applications and provision AWS infrastructure through simple API calls or a web dashboard.

## Live Deployment

- [Developer dashboard](https://compounds-tourism-convergence-induction.trycloudflare.com/dashboard/)
- [Interactive API documentation](https://compounds-tourism-convergence-induction.trycloudflare.com/docs)
- [Health check](https://compounds-tourism-convergence-induction.trycloudflare.com/healthz)
- [GitHub repository](https://github.com/dhamsey3/internal-developer-platform-api)

The hosted demo runs on an Ubuntu VM through a Cloudflare Quick Tunnel. The URL remains available while the `idp-cloudflare` service is running, but Cloudflare may assign a new hostname after the service or VM restarts.

### Use Cases

- **Self-service deployments**: Developers deploy Docker images without managing Kubernetes manifests
- **Infrastructure automation**: Provision AWS resources (EKS, networking, databases) via API
- **Multi-tenant environments**: Secure namespace isolation and RBAC
- **Real-time monitoring**: Track deployment status, logs, and cluster health
- **GitOps-ready**: Easily integrated with CI/CD pipelines and ArgoCD

---

## Quick Start

Get the IDP API running locally in 5 minutes:

```bash
# 1. Clone the repository
git clone https://github.com/dhamsey3/internal-developer-platform-api.git
cd internal-developer-platform-api

# 2. Create environment file (dry-run mode for local development)
cp .env.example .env

# 3. Install dependencies and run
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload

# 4. Open the dashboard
open http://127.0.0.1:8000/dashboard/

# 5. Explore API docs
open http://127.0.0.1:8000/docs
```

---

## Prerequisites

- **Python** 3.9 or later
- **Docker** (for containerized deployments)
- **Kubernetes** 1.24+ (optional, for local development use dry-run mode)
- **Terraform** 1.0+ (optional, for infrastructure provisioning)
- **PostgreSQL** or **SQLite** (SQLite for local development)

---

## Features

### Core Capabilities

- **Authentication & Authorization**
  - JWT-based authentication
  - Role-based access control (RBAC)
  - Rate limiting for API protection

- **Kubernetes Deployment Automation**
  - One-click application deployments
  - Auto-scaling configuration (HPA)
  - Namespace isolation
  - Service exposure via Ingress
  - Real-time pod logs and status

- **Cloud Infrastructure Provisioning**
  - AWS infrastructure via Terraform
  - EKS cluster provisioning
  - Async job queue for long-running tasks
  - State management with S3 + DynamoDB

- **Developer Dashboard**
  - Web UI for non-technical users
  - Template-based deployments
  - Real-time status tracking
  - Log viewing and metrics access

- **Observability**
  - Prometheus metrics
  - Grafana dashboards
  - Cluster health monitoring
  - Pod log aggregation

---

## Architecture

The API receives authenticated platform requests, validates input, stores metadata in the database, and orchestrates Kubernetes or Terraform operations through service-layer modules.

### Request Flow for Application Deployment

1. User authenticates with JWT
2. API validates Docker image, namespace, port, replica, ingress, and autoscaling inputs
3. A deployment row is created in the database
4. Kubernetes service layer creates namespace, Deployment, Service, Ingress, and HPA
5. Deployment status, URL, autoscaling settings, and errors are persisted
6. Users query deployment status, logs, metrics, and cluster health through API endpoints

---

## Project Structure

```text
app/              FastAPI app, configuration, logging
api/              Route handlers and Pydantic schemas
auth/             JWT, RBAC, rate limiting
database/         SQLAlchemy models and session lifecycle
services/         Kubernetes, Terraform, deployment, monitoring logic
web/              Developer dashboard served by FastAPI
kubernetes/       Cluster RBAC and network policy examples
terraform/        AWS Terraform templates
helm/             Helm chart for the API itself
monitoring/       Prometheus and Grafana examples
scripts/          Bootstrap, migration, production checklist helpers
tests/            Unit tests
```

---

## API Endpoints

### Authentication

- `POST /auth/register` - Register a new user
- `POST /auth/login` - Authenticate and receive JWT token
- `GET /auth/me` - Get current user info

### Infrastructure

- `POST /infrastructure/create` - Provision AWS infrastructure
- `GET /infrastructure/{id}` - Check infrastructure status
- `DELETE /infrastructure/{id}` - Destroy infrastructure

### Deployments

- `POST /deployments` - Deploy an application
- `GET /deployments/{id}` - Get deployment details
- `DELETE /deployments/{id}` - Delete a deployment

### Kubernetes Operations

- `POST /kubernetes/namespace/create` - Create a namespace
- `POST /kubernetes/service/expose` - Expose a service
- `POST /kubernetes/autoscaling/create` - Configure auto-scaling
- `POST /kubernetes/ingress/create` - Create ingress rules

### Monitoring

- `GET /monitoring/cluster/health` - Get cluster health status
- `GET /monitoring/metrics` - Prometheus metrics endpoint
- `GET /monitoring/logs/{pod}?namespace=default` - Retrieve pod logs

### Documentation

- `GET /docs` - Swagger/OpenAPI interactive documentation
- `GET /dashboard/` - Developer-friendly web dashboard

---

## Local Development

### Setup Environment

```bash
# Copy environment template
cp .env.example .env
```

For local development without a Kubernetes cluster or Terraform credentials, configure:

```bash
KUBERNETES_DRY_RUN=true
TERRAFORM_DRY_RUN=true
DATABASE_URL=sqlite:///./idp.db
ENABLE_PUBLIC_REGISTRATION=true
```

### Install & Run

```bash
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### Access the Dashboard

Open your browser and navigate to:
```
http://127.0.0.1:8000/dashboard/
```

The dashboard allows you to:
- Register and log in
- Deploy Docker images
- View deployment status
- Delete deployments
- Fetch pod logs
- Select from app templates and image catalogs

### Example API Calls

**Register a user:**
```bash
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"platform-user","password":"change-me-123"}'
```

**Login and get token:**
```bash
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"platform-user","password":"change-me-123"}' | jq -r .access_token)
```

**Deploy an application:**
```bash
curl -X POST http://localhost:8000/deployments \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "demo-api",
    "image": "nginx:1.25",
    "port": 80,
    "replicas": 2,
    "min_replicas": 1,
    "max_replicas": 5,
    "cpu_threshold": 70
  }'
```

---

## Terraform

The infrastructure API records requests, returns `202 Accepted`, and queues Terraform work for a worker that updates the infrastructure status. Local development can use the in-process background job.

### Production Setup

- Create an encrypted S3 backend bucket
- Create a DynamoDB lock table
- Replace `TERRAFORM_STATE_BUCKET` and `TERRAFORM_LOCK_TABLE` environment variables
- Use IAM roles with least privilege
- Review generated plans before production use
- For production, move the background job behind a durable queue or use Terraform Cloud, Atlantis, GitHub Actions, or Argo Workflows for plan approval and audit history
- Set `TERRAFORM_JOB_BACKEND=redis` and run the worker: `python -m services.infra_worker`

### Example Infrastructure Request

```bash
curl -X POST http://localhost:8000/infrastructure/create \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "platform-dev",
    "cloud_provider": "aws",
    "config": {
      "aws_region": "us-east-1",
      "eks_role_arn": "arn:aws:iam::123456789012:role/EKSClusterRole",
      "node_role_arn": "arn:aws:iam::123456789012:role/EKSNodeRole",
      "state_bucket": "company-terraform-state",
      "lock_table": "company-terraform-locks"
    }
  }'
```

Poll for status:
```bash
curl -X GET http://localhost:8000/infrastructure/{id} \
  -H "Authorization: Bearer $TOKEN"
```

---

## Helm Deployment

### Render the Helm Chart

```bash
helm template idp-api helm/charts/idp-api \
  --set secrets.databaseUrl='postgresql://user:pass@postgres:5432/idp' \
  --set secrets.secretKey='replace-with-long-random-secret'
```

### Install or Upgrade

```bash
helm upgrade --install idp-api helm/charts/idp-api \
  --set image.repository=registry.example.com/idp-api \
  --set image.tag=v1 \
  --set secrets.databaseUrl='postgresql://user:pass@postgres:5432/idp' \
  --set secrets.secretKey='replace-with-long-random-secret'
```

**Note:** The chart intentionally fails if `image.tag` is empty. Always use a release tag or digest, never `latest`.

---

## Security

### Implemented

- JWT authentication with token validation
- Role-aware user model and RBAC
- Protected infrastructure, deployment, Kubernetes, and monitoring APIs
- Redis-backed rate limiting with local fallback
- Non-root Docker container
- Security headers and restricted CORS origin configuration
- Production startup validation for weak/default `SECRET_KEY`
- Helm defaults: public registration disabled, debug disabled, read-only root filesystem, dropped Linux capabilities
- Kubernetes RBAC and network-policy examples
- No hardcoded production secret requirement in Helm

### Recommended for Production

- Use AWS Secrets Manager, External Secrets Operator, or sealed-secrets
- Keep public registration disabled unless you implement an invite/admin onboarding flow
- Replace SQLite with managed PostgreSQL
- Use Alembic for database migrations
- Run Terraform through Redis worker queue, Terraform Cloud, Atlantis, GitHub Actions, or Argo Workflows with audit history
- Enforce tenant-aware namespace ownership
- Add admission policies with Kyverno or OPA Gatekeeper
- Use image allowlists and vulnerability scanning
- Require immutable image digests for production deployments

---

## Observability

The API exposes Prometheus metrics at `/monitoring/metrics`. Example scrape configuration and Grafana dashboard starters live in the `monitoring/` directory.

### Recommended Production Stack

- Prometheus Operator
- Grafana dashboards for API latency, error rate, Kubernetes deployment state, and Terraform failures
- Loki or OpenSearch for structured logs
- Alertmanager alerts for failed provisions, high error rate, and unhealthy clusters

---

## CI/CD

The GitHub Actions workflow installs dependencies, runs linting/tests, and builds the Docker image. Registry push and Kubernetes deployment stages are intentionally left as placeholders until you configure your registry and cluster access.

---

## Implementation Phases

- **Phase 1**: Architecture and folder structure with layered app layout
- **Phase 2**: FastAPI backend with auth, validation, database models, OpenAPI, health checks, and rate limiting
- **Phase 3**: Kubernetes integration for namespaces, deployments, services, ingress, HPA, status, logs, and safe deletes
- **Phase 4**: Terraform automation for AWS templates with apply/destroy and remote-state configuration
- **Phase 5**: Monitoring with Prometheus metrics, cluster health, pod logs, and dashboard examples
- **Phase 6**: CI/CD with linting, testing, and Docker image build
- **Phase 7**: Production hardening (see `scripts/prod_checklist.md`)

---

## Scaling Recommendations

- Move long-running deploy/provision tasks to Celery, RQ, Temporal, or Argo Workflows
- Add per-tenant quotas for namespaces, replicas, CPU, memory, and load balancers
- Use GitOps with ArgoCD for reconciliation and auditability
- Split API, worker, scheduler, and webhook receiver into separate deployments
- Use PostgreSQL with row-level ownership checks and explicit tenant IDs
- Add blue/green and canary deployment strategies with Argo Rollouts or Flagger

---

## Troubleshooting

### Issue: "Kubernetes connection failed" in dry-run mode

**Solution**: Ensure `KUBERNETES_DRY_RUN=true` is set in your `.env` file for local development.

### Issue: Dashboard not loading

**Solution**: Make sure the FastAPI server is running and accessible at `http://127.0.0.1:8000`. Check firewall settings.

### Issue: Deployment fails with authentication error

**Solution**: Verify your JWT token is valid by calling `GET /auth/me` with your token.

### Issue: Terraform state lock error

**Solution**: Ensure DynamoDB lock table exists and your IAM credentials have proper permissions.

---

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/your-feature`)
3. Commit your changes (`git commit -m 'Add your feature'`)
4. Push to the branch (`git push origin feature/your-feature`)
5. Open a Pull Request

Please ensure:
- Code follows PEP 8 standards
- Tests pass (`pytest`)
- Documentation is updated
- Security best practices are followed

---

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

---

## Support

For issues, questions, or feedback:
- Open an [Issue](https://github.com/dhamsey3/internal-developer-platform-api/issues)
- Check existing [Discussions](https://github.com/dhamsey3/internal-developer-platform-api/discussions)
- Review the [Security Policy](SECURITY.md)

---

**Built with ❤️ for DevOps and Cloud Engineers**
