# Cloud Infrastructure Provisioning API

This project is an Internal Developer Platform API built on FastAPI, Kubernetes, Terraform, PostgreSQL/SQLite, Redis, Helm, Prometheus, Grafana, and JWT authentication. It extends the original Kubernetes manifests into a mini Heroku/Render/Railway-style platform for provisioning infrastructure and deploying containerized applications through REST APIs.

## Architecture

The API receives authenticated platform requests, validates input, stores metadata in the database, and orchestrates Kubernetes or Terraform operations through service-layer modules.

Request flow for application deployment:

1. User authenticates with JWT.
2. API validates Docker image, namespace, port, replica, ingress, and autoscaling inputs.
3. A deployment row is created in the database.
4. Kubernetes service layer creates namespace, Deployment, Service, Ingress, and HPA.
5. Deployment status, URL, autoscaling settings, and errors are persisted.
6. Users query deployment status, logs, metrics, and cluster health through API endpoints.

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

## API Endpoints

Auth:

- `POST /auth/register`
- `POST /auth/login`
- `GET /auth/me`

Infrastructure:

- `POST /infrastructure/create`
- `GET /infrastructure/{id}`
- `DELETE /infrastructure/{id}`

Deployments:

- `POST /deployments`
- `GET /deployments/{id}`
- `DELETE /deployments/{id}`

Kubernetes:

- `POST /namespace/create`
- `POST /service/expose`
- `POST /autoscaling/create`
- `POST /kubernetes/ingress/create`

Monitoring:

- `GET /cluster/health`
- `GET /metrics`
- `GET /logs/{pod}?namespace=default`

Swagger/OpenAPI is available at `/docs`.

The developer dashboard is available at `/dashboard/`.

## Local Development

Create an environment file:

```bash
cp .env.example .env
```

For local development without a Kubernetes cluster or Terraform credentials, keep:

```bash
KUBERNETES_DRY_RUN=true
TERRAFORM_DRY_RUN=true
DATABASE_URL=sqlite:///./idp.db
```

Install dependencies and run the API:

```bash
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt
./.venv/bin/uvicorn app.main:app --reload
```

Open the dashboard:

```text
http://127.0.0.1:8000/dashboard/
```

The dashboard lets developers register/login, deploy Docker images, see app status, delete deployments, and fetch pod logs.

Register and log in:

```bash
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"platform-user","password":"change-me-123"}'

TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"platform-user","password":"change-me-123"}' | jq -r .access_token)
```

Deploy an application:

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

## Terraform

The infrastructure API renders [terraform/main.tf.j2](terraform/main.tf.j2) and can create or destroy AWS resources. It is dry-run by default. Before enabling real execution:

- Create an encrypted S3 backend bucket.
- Create a DynamoDB lock table.
- Replace `TERRAFORM_STATE_BUCKET` and `TERRAFORM_LOCK_TABLE`.
- Use IAM roles with least privilege.
- Review generated plans before production use.

Example:

```bash
curl -X POST http://localhost:8000/infrastructure/create \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "platform-dev",
    "cloud_provider": "aws",
    "config": {
      "aws_region": "us-east-1",
      "eks_role_arn": "arn:aws:iam::123456789012:role/EKSRole"
    }
  }'
```

## Helm Deployment

Render or install the API chart:

```bash
helm template idp-api helm/charts/idp-api \
  --set secrets.databaseUrl='postgresql://user:pass@postgres:5432/idp' \
  --set secrets.secretKey='replace-with-long-random-secret'

helm upgrade --install idp-api helm/charts/idp-api \
  --set image.repository=registry.example.com/idp-api \
  --set image.tag=v1 \
  --set secrets.databaseUrl='postgresql://user:pass@postgres:5432/idp' \
  --set secrets.secretKey='replace-with-long-random-secret'
```

## Security

Implemented:

- JWT authentication
- Role-aware user model
- Protected infrastructure, deployment, Kubernetes, and monitoring APIs
- Redis-backed rate limiting with local fallback
- Non-root Docker container
- Kubernetes RBAC and network-policy examples
- No hardcoded production secret requirement in Helm

Recommended before production:

- Use AWS Secrets Manager, External Secrets Operator, or sealed-secrets.
- Replace SQLite with managed PostgreSQL.
- Use Alembic migrations.
- Run Terraform through a job queue or workflow engine rather than synchronous HTTP requests.
- Enforce tenant-aware namespace ownership.
- Add admission policies with Kyverno or OPA Gatekeeper.
- Use image allowlists and vulnerability scanning.
- Require immutable image digests for production deployments.

## Observability

The API exposes Prometheus metrics at `/metrics`. Example scrape configuration and a Grafana dashboard starter live in `monitoring/`.

Recommended production stack:

- Prometheus Operator
- Grafana dashboards for API latency, error rate, Kubernetes deployment state, and Terraform failures
- Loki or OpenSearch for structured logs
- Alertmanager alerts for failed provisions, high error rate, and unhealthy clusters

## CI/CD

The GitHub Actions workflow installs dependencies, runs linting/tests, and builds the Docker image. Registry push and Kubernetes deployment are intentionally placeholders until registry, cluster, and secret strategy are configured.

## Implementation Phases

Phase 1: Architecture and folder structure are represented by the layered app layout.

Phase 2: FastAPI backend includes auth, validation, database models, OpenAPI, health checks, and rate limiting.

Phase 3: Kubernetes integration creates namespaces, deployments, services, ingress, HPA, status, logs, and safe deletes.

Phase 4: Terraform automation renders AWS templates and supports apply/destroy with remote-state configuration.

Phase 5: Monitoring exposes Prometheus metrics, cluster health, pod logs, and dashboard examples.

Phase 6: CI/CD builds, lints, tests, and prepares image/deployment stages.

Phase 7: Production hardening is documented in `scripts/prod_checklist.md` and should be completed before real cloud use.

## Scaling Recommendations

- Move long-running deploy/provision tasks to Celery, RQ, Temporal, or Argo Workflows.
- Add per-tenant quotas for namespaces, replicas, CPU, memory, and load balancers.
- Use GitOps with ArgoCD for reconciliation and auditability.
- Split API, worker, scheduler, and webhook receiver into separate deployments.
- Use PostgreSQL row-level ownership checks and explicit tenant IDs.
- Add blue/green and canary deployment strategies with Argo Rollouts or Flagger.
