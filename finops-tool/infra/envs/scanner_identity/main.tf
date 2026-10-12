# Scanner identity for running FinOps Tool on your own machine WITHOUT SSO.
# Apply once, in the account your operator IAM user lives in, with that user's
# profile. Creates the FinOps-Scanner role: your user may assume it, and it
# may only sts:AssumeRole into roles named FinOps-ReadOnly* in any account. That is
# the whole grant, once for all customers: each customer's own role trusts this
# exact role ARN and requires that account's unique ExternalId.
#
# The operator user's long-lived keys stay on the host (Terraform, aws CLI).
# scripts/refresh_scanner_credentials.sh mints 12 h credentials of this role
# into a separate directory, and only that directory is mounted into Docker.
#
#   cp terraform.tfvars.example terraform.tfvars   # fill in
#   terraform init && terraform apply     # once; nothing to do per customer

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
  region  = "us-east-1" # IAM is global
  profile = var.aws_profile

  default_tags {
    tags = {
      Project   = "finops-tool"
      ManagedBy = "terraform"
    }
  }
}

variable "aws_profile" {
  description = "Operator profile (IAM user) in the scanner account"
  type        = string
  default     = null
}

variable "expected_account_id" {
  description = "Guard: the 12-digit account the profile must resolve to"
  type        = string
}

variable "operator_arn" {
  description = "IAM user/role allowed to assume the scanner role (default: the caller)"
  type        = string
  default     = null
}

variable "role_name" {
  type    = string
  default = "FinOps-Scanner"
}

data "aws_caller_identity" "current" {
  lifecycle {
    postcondition {
      condition     = self.account_id == var.expected_account_id
      error_message = "aws_profile points to a different account than expected_account_id."
    }
  }
}

locals {
  operator_arn = coalesce(var.operator_arn, data.aws_caller_identity.current.arn)
}

data "aws_iam_policy_document" "trust" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]
    principals {
      type        = "AWS"
      identifiers = [local.operator_arn]
    }
  }
}

data "aws_iam_policy_document" "assume_targets" {
  # Must match services/common/aws_access.py SOURCE_ASSUME_RESOURCE.
  statement {
    sid       = "AssumeFinOpsTargetRoles"
    actions   = ["sts:AssumeRole"]
    resources = ["arn:aws:iam::*:role/FinOps-ReadOnly*"]
  }
}

resource "aws_iam_role" "scanner" {
  name                 = var.role_name
  description          = "FinOps Tool scanner source identity; can only assume FinOps Tool read-only roles"
  assume_role_policy   = data.aws_iam_policy_document.trust.json
  max_session_duration = 43200

  lifecycle {
    precondition {
      condition     = can(regex("^arn:aws:iam::[0-9]{12}:(user|role)/", local.operator_arn))
      error_message = "The operator must be an IAM user or role ARN (set operator_arn when running as an assumed role)."
    }
  }
}

resource "aws_iam_role_policy" "assume_targets" {
  name   = "finops-assume-targets"
  role   = aws_iam_role.scanner.id
  policy = data.aws_iam_policy_document.assume_targets.json
}

output "scanner_role_arn" {
  description = "SCANNER_ROLE_ARN in .env; host_role_arn in member_account tfvars"
  value       = aws_iam_role.scanner.arn
}
