# Production Readiness Checklist for IDP API

## Infrastructure
- [ ] Terraform S3 backend configured
- [ ] AWS resources provisioned (VPC, EKS, IAM)
- [ ] EKS API public access restricted to approved `/32` or corporate CIDRs
- [ ] Private subnet NAT strategy selected (`single_nat_gateway=false` for zonal high availability)
- [ ] Supported EKS Kubernetes version selected
- [ ] Terraform state bucket secured
- [ ] Terraform worker deployed with `TERRAFORM_JOB_BACKEND=redis`
- [ ] Redis job queue monitored and backed up according to environment needs

## Kubernetes
- [ ] Ingress controller deployed (NGINX/ALB)
- [ ] Prometheus and Grafana installed
- [ ] RBAC and ServiceAccount applied
- [ ] NetworkPolicy applied
- [ ] Secrets created and referenced
- [ ] App deployed via Helm
- [ ] HTTPS enforced at ingress
- [ ] API image tag pinned to a release tag or digest
- [ ] Pod and container security contexts enabled

## Application
- [ ] All secrets from env/K8s Secrets
- [ ] `SECRET_KEY` is a random value of at least 32 characters
- [ ] `APP_DEBUG=false` in production
- [ ] `ENABLE_PUBLIC_REGISTRATION=false` unless intentionally offering self-service signup
- [ ] `ALLOWED_ORIGINS` restricted to trusted dashboard origins
- [ ] JWT, RBAC, rate limiting enabled
- [ ] Liveness/readiness probes configured
- [ ] Structured logging enabled
- [ ] Prometheus metrics exposed

## CI/CD
- [ ] GitHub Actions for build/test/deploy
- [ ] Security scanning (Trivy/Snyk)
- [ ] Automated DB migrations

## Observability
- [ ] Prometheus scraping `/monitoring/metrics`
- [ ] Grafana dashboards imported
- [ ] Alerting configured

## Security
- [ ] HTTPS everywhere
- [ ] RBAC and network policies
- [ ] Non-root containers
- [ ] Read-only root filesystem where supported
- [ ] Regular secret rotation

## Advanced
- [ ] Multi-tenancy (namespaces, RBAC)
- [ ] GitOps (ArgoCD/Flux)
- [ ] Cost estimation
- [ ] Canary/blue-green deployments
