import os
import subprocess
import tempfile
from jinja2 import Template
from app.config import settings

TERRAFORM_TEMPLATE = os.path.join(os.path.dirname(__file__), '../terraform/main.tf.j2')


def render_terraform_config(context: dict) -> str:
    with open(TERRAFORM_TEMPLATE) as f:
        template = Template(f.read())
    return template.render(**context)


def run_terraform(directory: str, action: str = 'apply'):
    if settings.TERRAFORM_DRY_RUN:
        return True
    cmds = [
        ['terraform', 'init'],
        ['terraform', 'plan', '-out=tfplan'],
        ['terraform', 'apply', '-auto-approve', 'tfplan']
        if action == 'apply'
        else ['terraform', 'destroy', '-auto-approve']
    ]
    for cmd in cmds:
        proc = subprocess.run(cmd, cwd=directory, capture_output=True, text=True, timeout=1800)
        if proc.returncode != 0:
            raise Exception(f"Terraform {cmd[1]} failed: {proc.stderr}")
    return True


def provision_infrastructure(name: str, cloud_provider: str, config: dict):
    context = {
        'aws_region': config.get('aws_region', settings.AWS_REGION),
        'cluster_name': name,
        'eks_role_arn': config.get('eks_role_arn', 'arn:aws:iam::123456789012:role/EKSRole'),
        'state_bucket': config.get('state_bucket', settings.TERRAFORM_STATE_BUCKET),
        'lock_table': config.get('lock_table', settings.TERRAFORM_LOCK_TABLE),
    }
    with tempfile.TemporaryDirectory() as tmpdir:
        tf_path = os.path.join(tmpdir, 'main.tf')
        with open(tf_path, 'w') as f:
            f.write(render_terraform_config(context))
        try:
            run_terraform(tmpdir, 'apply')
            return True
        except Exception as e:
            return str(e)


def destroy_infrastructure(name: str, cloud_provider: str, config: dict):
    context = {
        'aws_region': config.get('aws_region', settings.AWS_REGION),
        'cluster_name': name,
        'eks_role_arn': config.get('eks_role_arn', 'arn:aws:iam::123456789012:role/EKSRole'),
        'state_bucket': config.get('state_bucket', settings.TERRAFORM_STATE_BUCKET),
        'lock_table': config.get('lock_table', settings.TERRAFORM_LOCK_TABLE),
    }
    with tempfile.TemporaryDirectory() as tmpdir:
        tf_path = os.path.join(tmpdir, 'main.tf')
        with open(tf_path, 'w') as f:
            f.write(render_terraform_config(context))
        try:
            run_terraform(tmpdir, 'destroy')
            return True
        except Exception as e:
            return str(e)
