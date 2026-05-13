# Production Readiness Checklist for IDP API

## Infrastructure
- [ ] Terraform S3 backend configured
- [ ] AWS resources provisioned (VPC, EKS, IAM)
- [ ] Terraform state bucket secured

## Kubernetes
- [ ] Ingress controller deployed (NGINX/ALB)
- [ ] Prometheus and Grafana installed
- [ ] RBAC and ServiceAccount applied
- [ ] NetworkPolicy applied
- [ ] Secrets created and referenced
- [ ] App deployed via Helm
- [ ] HTTPS enforced at ingress

## Application
- [ ] All secrets from env/K8s Secrets
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
- [ ] Regular secret rotation

## Advanced
- [ ] Multi-tenancy (namespaces, RBAC)
- [ ] GitOps (ArgoCD/Flux)
- [ ] Cost estimation
- [ ] Canary/blue-green deployments
