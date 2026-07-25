from types import SimpleNamespace

from services.infra_service import (
    _build_context,
    check_aws_prerequisites,
    provision_infrastructure,
    render_terraform_config,
    validate_infrastructure_config,
)
from services.infra_queue import decode_job


VALID_CONFIG = {
    "aws_region": "us-east-1",
    "state_bucket": "company-terraform-state",
    "lock_table": "company-terraform-locks",
    "public_access_cidrs": ["203.0.113.10/32"],
}


def test_infra_requires_real_backend():
    result = provision_infrastructure("platform-dev", "aws", {"aws_region": "us-east-1"})
    assert "Terraform backend" in result


def test_infra_validation_catches_bad_requests_before_queueing():
    result = validate_infrastructure_config("platform-dev", "aws", {"aws_region": "us-east-1"})
    assert "Terraform backend" in result


def test_rendered_terraform_has_professional_eks_defaults():
    context = _build_context("platform-dev", VALID_CONFIG)
    rendered = render_terraform_config(context)

    assert 'required_version = ">= 1.6.0"' in rendered
    assert 'resource "aws_eks_node_group" "main"' in rendered
    assert "endpoint_public_access  = true" in rendered
    assert 'public_access_cidrs     = ["203.0.113.10/32"]' in rendered
    assert 'enabled_cluster_log_types = ["api", "audit", "authenticator"]' in rendered
    assert "node_role_arn   = aws_iam_role.eks_node.arn" in rendered
    assert 'resource "aws_iam_role" "eks_cluster"' in rendered
    assert 'resource "aws_iam_role" "eks_node"' in rendered
    assert "aws_subnet.private" in rendered
    assert 'resource "aws_nat_gateway" "main"' in rendered
    assert 'resource "aws_route_table" "private"' in rendered


def test_public_eks_endpoint_rejects_world_access():
    config = {**VALID_CONFIG, "public_access_cidrs": ["0.0.0.0/0"]}
    result = validate_infrastructure_config("platform-dev", "aws", config)
    assert "must not expose the EKS API" in result


def test_aws_preflight_checks_identity_and_backend(monkeypatch):
    monkeypatch.setattr("services.infra_service.shutil.which", lambda command: f"/usr/bin/{command}")
    monkeypatch.setattr(
        "services.infra_service.subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout="{}", stderr=""),
    )

    result = check_aws_prerequisites("platform-dev", VALID_CONFIG)

    assert result["ready"] is True
    assert all(result["checks"].values())


def test_decode_infrastructure_queue_job():
    payload = decode_job(b'{"action":"provision","infrastructure_id":42}')
    assert payload["action"] == "provision"
    assert payload["infrastructure_id"] == 42
