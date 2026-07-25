import argparse
from pathlib import Path

from services.infra_service import _build_context, render_terraform_config


def main() -> None:
    parser = argparse.ArgumentParser(description="Render the AWS EKS Terraform configuration")
    parser.add_argument("--cluster-name", required=True)
    parser.add_argument("--aws-region", required=True)
    parser.add_argument("--state-bucket", required=True)
    parser.add_argument("--public-access-cidr", required=True)
    parser.add_argument("--output", default="main.tf")
    args = parser.parse_args()

    context = _build_context(
        args.cluster_name,
        {
            "aws_region": args.aws_region,
            "state_bucket": args.state_bucket,
            "public_access_cidrs": [args.public_access_cidr],
            "single_nat_gateway": True,
            "node_min_size": 1,
            "node_desired_size": 1,
            "node_max_size": 2,
        },
    )
    Path(args.output).write_text(render_terraform_config(context))


if __name__ == "__main__":
    main()
