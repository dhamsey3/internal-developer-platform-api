import ipaddress
import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from jinja2 import StrictUndefined, Template

from app.config import settings

TERRAFORM_TEMPLATE = Path(__file__).resolve().parent.parent / "terraform" / "main.tf.j2"
AWS_REGION_RE = re.compile(r"^[a-z]{2}-[a-z]+-\d$")
IAM_ROLE_ARN_RE = re.compile(r"^arn:aws:iam::\d{12}:role\/[A-Za-z0-9+=,.@_/-]+$")
DEFAULT_CLUSTER_VERSION = "1.34"
DEFAULT_NODE_INSTANCE_TYPES = ["t3.medium"]
DEFAULT_TAGS = {
    "ManagedBy": "idp-api",
    "Project": "internal-developer-platform",
}


def render_terraform_config(context: dict[str, Any]) -> str:
    with open(TERRAFORM_TEMPLATE) as f:
        template = Template(f.read(), undefined=StrictUndefined)
    return template.render(**context)


def run_terraform(directory: str, action: str = 'apply'):
    if settings.TERRAFORM_DRY_RUN:
        return True
    if action not in {"apply", "destroy"}:
        raise ValueError("Unsupported Terraform action")
    cmds = [
        ['terraform', 'init', '-input=false'],
        ['terraform', 'validate'],
        ['terraform', 'plan', '-input=false', '-lock-timeout=5m', '-out=tfplan'],
        ['terraform', 'apply', '-input=false', '-lock-timeout=5m', '-auto-approve', 'tfplan']
        if action == 'apply'
        else ['terraform', 'destroy', '-input=false', '-lock-timeout=5m', '-auto-approve']
    ]
    for cmd in cmds:
        proc = subprocess.run(cmd, cwd=directory, capture_output=True, text=True, timeout=1800)
        if proc.returncode != 0:
            stderr = proc.stderr.strip() or proc.stdout.strip()
            raise RuntimeError(f"Terraform {cmd[1]} failed: {stderr}")
    return True


def configure_eks_kubeconfig(cluster_name: str, aws_region: str) -> None:
    if settings.TERRAFORM_DRY_RUN:
        return
    proc = subprocess.run(
        [
            "aws",
            "eks",
            "update-kubeconfig",
            "--name",
            cluster_name,
            "--region",
            aws_region,
            "--alias",
            cluster_name,
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if proc.returncode != 0:
        stderr = proc.stderr.strip() or proc.stdout.strip()
        raise RuntimeError(f"Failed to configure EKS kubeconfig: {stderr}")


def _validate_cidr(value: str, field_name: str, *, require_ipv4: bool = True) -> str:
    try:
        network = ipaddress.ip_network(value)
    except ValueError as exc:
        raise ValueError(f"{field_name} must be a valid CIDR block") from exc
    if require_ipv4 and network.version != 4:
        raise ValueError(f"{field_name} must be an IPv4 CIDR block")
    return value


def _string_list(value: Any, field_name: str, default: list[str]) -> list[str]:
    if value is None:
        return default
    if not isinstance(value, list) or not value or not all(isinstance(item, str) and item for item in value):
        raise ValueError(f"{field_name} must be a non-empty list of strings")
    return value


def _build_context(name: str, config: dict[str, Any]) -> dict[str, Any]:
    aws_region = config.get("aws_region", settings.AWS_REGION)
    if not AWS_REGION_RE.match(aws_region):
        raise ValueError("aws_region must look like a valid AWS region, for example us-east-1")

    eks_role_arn = config.get("eks_role_arn")
    if not eks_role_arn or not IAM_ROLE_ARN_RE.match(eks_role_arn):
        raise ValueError("eks_role_arn is required and must be a valid IAM role ARN")
    node_role_arn = config.get("node_role_arn")
    if not node_role_arn or not IAM_ROLE_ARN_RE.match(node_role_arn):
        raise ValueError("node_role_arn is required and must be a valid IAM role ARN")

    state_bucket = config.get("state_bucket", settings.TERRAFORM_STATE_BUCKET)
    lock_table = config.get("lock_table", settings.TERRAFORM_LOCK_TABLE)
    if state_bucket == "replace-me-terraform-state" or lock_table == "replace-me-terraform-locks":
        raise ValueError("Terraform backend state_bucket and lock_table must be configured")

    public_subnet_cidrs = _string_list(
        config.get("public_subnet_cidrs"),
        "public_subnet_cidrs",
        ["10.0.0.0/20", "10.0.16.0/20"],
    )
    private_subnet_cidrs = _string_list(
        config.get("private_subnet_cidrs"),
        "private_subnet_cidrs",
        ["10.0.128.0/20", "10.0.144.0/20"],
    )
    if len(public_subnet_cidrs) < 2 or len(private_subnet_cidrs) < 2:
        raise ValueError("EKS requires at least two public and two private subnet CIDRs")

    node_min_size = int(config.get("node_min_size", 1))
    node_desired_size = int(config.get("node_desired_size", 2))
    node_max_size = int(config.get("node_max_size", 4))
    if not node_min_size <= node_desired_size <= node_max_size:
        raise ValueError("node sizing must satisfy node_min_size <= node_desired_size <= node_max_size")

    endpoint_public_access = bool(config.get("endpoint_public_access", True))
    public_access_cidrs = _string_list(
        config.get("public_access_cidrs"),
        "public_access_cidrs",
        [],
    ) if endpoint_public_access else []
    if endpoint_public_access and not public_access_cidrs:
        raise ValueError("public_access_cidrs is required when endpoint_public_access is true")
    validated_public_access_cidrs = [
        _validate_cidr(cidr, "public_access_cidrs") for cidr in public_access_cidrs
    ]
    if "0.0.0.0/0" in validated_public_access_cidrs:
        raise ValueError("public_access_cidrs must not expose the EKS API to 0.0.0.0/0")

    custom_tags = config.get("tags", {})
    if not isinstance(custom_tags, dict):
        raise ValueError("tags must be an object with string keys and values")
    if not all(isinstance(k, str) and isinstance(v, str) for k, v in custom_tags.items()):
        raise ValueError("tags must be an object with string keys and values")

    tags = {**DEFAULT_TAGS, **custom_tags}
    return {
        "aws_region": aws_region,
        "cluster_name": name,
        "cluster_version": config.get("cluster_version", DEFAULT_CLUSTER_VERSION),
        "eks_role_arn": eks_role_arn,
        "node_role_arn": node_role_arn,
        "state_bucket": state_bucket,
        "lock_table": lock_table,
        "vpc_cidr": _validate_cidr(config.get("vpc_cidr", "10.0.0.0/16"), "vpc_cidr"),
        "public_subnet_cidrs": [_validate_cidr(cidr, "public_subnet_cidrs") for cidr in public_subnet_cidrs],
        "private_subnet_cidrs": [_validate_cidr(cidr, "private_subnet_cidrs") for cidr in private_subnet_cidrs],
        "endpoint_public_access": endpoint_public_access,
        "endpoint_private_access": bool(config.get("endpoint_private_access", True)),
        "public_access_cidrs": validated_public_access_cidrs,
        "single_nat_gateway": bool(config.get("single_nat_gateway", True)),
        "enabled_cluster_log_types": _string_list(
            config.get("enabled_cluster_log_types"),
            "enabled_cluster_log_types",
            ["api", "audit", "authenticator"],
        ),
        "node_instance_types": _string_list(
            config.get("node_instance_types"),
            "node_instance_types",
            DEFAULT_NODE_INSTANCE_TYPES,
        ),
        "node_desired_size": node_desired_size,
        "node_min_size": node_min_size,
        "node_max_size": node_max_size,
        "tags": tags,
    }


def validate_infrastructure_config(name: str, cloud_provider: str, config: dict[str, Any]) -> str | None:
    if cloud_provider != "aws":
        return "Unsupported cloud provider"
    try:
        _build_context(name, config)
    except ValueError as exc:
        return str(exc)
    return None


def provision_infrastructure(name: str, cloud_provider: str, config: dict):
    if cloud_provider != "aws":
        return "Unsupported cloud provider"
    try:
        context = _build_context(name, config)
    except ValueError as exc:
        return str(exc)
    with tempfile.TemporaryDirectory() as tmpdir:
        tf_path = os.path.join(tmpdir, 'main.tf')
        with open(tf_path, 'w') as f:
            f.write(render_terraform_config(context))
        try:
            run_terraform(tmpdir, 'apply')
            configure_eks_kubeconfig(context["cluster_name"], context["aws_region"])
            return True
        except Exception as e:
            return str(e)


def destroy_infrastructure(name: str, cloud_provider: str, config: dict):
    if cloud_provider != "aws":
        return "Unsupported cloud provider"
    try:
        context = _build_context(name, config)
    except ValueError as exc:
        return str(exc)
    with tempfile.TemporaryDirectory() as tmpdir:
        tf_path = os.path.join(tmpdir, 'main.tf')
        with open(tf_path, 'w') as f:
            f.write(render_terraform_config(context))
        try:
            run_terraform(tmpdir, 'destroy')
            return True
        except Exception as e:
            return str(e)
