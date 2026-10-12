# Optional, for accounts YOU own (e.g. the FinOps Tool account itself). Customer
# accounts create this role themselves from the dashboard (CLI/CloudFormation/
# console). Creates only the read-only, ExternalId-gated role the scanner assumes.
#
#   cp terraform.tfvars.example accounts/<name>.tfvars   # fill in
#   terraform init
#   terraform workspace new <name>        # one state per account
#   terraform apply -var-file=accounts/<name>.tfvars
#
# See docs/LAB.md for the lab workflow.

terraform {
  required_version = ">= 1.7"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region  = "us-east-1" # IAM is global; any region works
  profile = var.aws_profile

  default_tags {
    tags = {
      Project   = "finops-tool"
      ManagedBy = "terraform"
    }
  }
}

variable "aws_profile" {
  description = "AWS CLI profile with admin access to THIS target account; null = default chain"
  type        = string
  default     = null
}

variable "expected_account_id" {
  description = "Guard: the 12-digit account the profile must resolve to"
  type        = string
}

variable "host_role_arn" {
  description = "Scanner identity as an explicit role ARN (envs/scanner_identity output, or envs/host instance_role_arn)"
  type        = string
  default     = null
}

variable "trusted_principal_arn_pattern" {
  description = "Scanner identity when it is an SSO role (shown on the dashboard account page)"
  type        = string
  default     = null
}

variable "account_name" {
  description = "Friendly name for this account in FinOps Tool, e.g. lab-a"
  type        = string
}

variable "external_id" {
  description = "ExternalId shown on the dashboard account page (or scripts.admin gen-external-id)"
  type        = string
  sensitive   = true
}

variable "role_name" {
  description = "Must match the dashboard role name; must start with FinOps-ReadOnly"
  type        = string
  default     = "FinOps-ReadOnly"
}

data "aws_caller_identity" "current" {
  lifecycle {
    postcondition {
      condition     = self.account_id == var.expected_account_id
      error_message = "aws_profile points to a different account than expected_account_id."
    }
  }
}

module "role" {
  source                        = "../../modules/onboarding_role"
  trusted_role_arn              = var.host_role_arn
  trusted_principal_arn_pattern = var.trusted_principal_arn_pattern
  external_id                   = var.external_id
  tenant_name                   = var.account_name
  role_name                     = var.role_name

  depends_on = [data.aws_caller_identity.current]
}

output "role_arn" { value = module.role.role_arn }
