# Waste lab: create cheap, deliberately wasteful resources in one of YOUR test
# accounts, run a real FinOps Tool scan, verify the findings, then destroy.
# One Terraform workspace (= one state) per account. Full workflow: docs/LAB.md
#
#   cp terraform.tfvars.example accounts/<name>.tfvars    # fill in
#   terraform init
#   terraform workspace new <name>          # later: terraform workspace select <name>
#   terraform apply   -var-file=accounts/<name>.tfvars
#   terraform output -json lab > /tmp/lab-<name>.json     # for scripts.lab_verify
#   terraform destroy -var-file=accounts/<name>.tfvars
#
# Cost while it exists (defaults): ~2 GiB EBS + 2 public IPv4 ≈ $0.01/hour.

terraform {
  required_version = ">= 1.7"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

locals {
  tags = {
    Project   = "finops-tool"
    Purpose   = "finops-lab"
    Lab       = var.lab_name
    ManagedBy = "terraform"
  }
}

provider "aws" {
  region  = var.region
  profile = var.aws_profile
  default_tags { tags = local.tags }
}

# Only used when secondary_region is set (tests multi-region discovery).
provider "aws" {
  alias   = "secondary"
  region  = coalesce(var.secondary_region, var.region)
  profile = var.aws_profile
  default_tags { tags = local.tags }
}

data "aws_caller_identity" "current" {
  lifecycle {
    postcondition {
      condition     = self.account_id == var.expected_account_id
      error_message = "aws_profile points to a different account than expected_account_id."
    }
  }
}

module "primary" {
  source            = "../../modules/waste_lab"
  lab_name          = var.lab_name
  orphan_volumes    = var.orphan_volumes
  unassociated_eips = var.unassociated_eips
  create_controls   = var.create_controls

  depends_on = [data.aws_caller_identity.current]
}

module "secondary" {
  source            = "../../modules/waste_lab"
  count             = var.secondary_region == null ? 0 : 1
  providers         = { aws = aws.secondary }
  lab_name          = "${var.lab_name}-2"
  orphan_volumes    = [{ type = "gp3", size_gb = 1 }]
  unassociated_eips = 0
  create_controls   = false

  depends_on = [data.aws_caller_identity.current]
}

output "lab" {
  description = "Input for: python -m scripts.lab_verify"
  value = {
    aws_account_id    = data.aws_caller_identity.current.account_id
    expected_findings = concat(module.primary.expected_findings, flatten(module.secondary[*].expected_findings))
    controls          = concat(module.primary.controls, flatten(module.secondary[*].controls))
  }
}
