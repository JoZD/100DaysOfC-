# Apply ONCE, in the company AWS account that will host FinOps Tool.
# Creates the server, and the read-only role so the host account scans itself.
#
#   cp terraform.tfvars.example terraform.tfvars   # fill in
#   terraform init && terraform apply

terraform {
  required_version = ">= 1.7"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
  # Recommended: keep state in a company S3 bucket.
  # backend "s3" { bucket = "..." key = "finops/host.tfstate" region = "..." }
}

provider "aws" {
  region = var.region
}

variable "region" {
  type    = string
  default = "us-east-1"
}
variable "vpc_id" { type = string }
variable "subnet_id" { type = string }
variable "associate_public_ip" {
  type    = bool
  default = false
}
variable "host_name" {
  description = "Resource name prefix; keep stable once applied"
  type        = string
  default     = "finops"
}
variable "host_scan_role_name" {
  description = "Optional existing self-scan role name to preserve"
  type        = string
  default     = null
}
variable "host_account_external_id" {
  description = "ExternalId for scanning THIS account (python -m scripts.admin gen-external-id)"
  type        = string
  sensitive   = true
}
variable "host_account_name" {
  description = "Friendly name for this account in FinOps Tool, e.g. shared-services"
  type        = string
}

data "aws_caller_identity" "current" {}

module "host" {
  source              = "../../modules/platform_host"
  vpc_id              = var.vpc_id
  subnet_id           = var.subnet_id
  associate_public_ip = var.associate_public_ip
  name                = var.host_name
}

module "self_scan_role" {
  source           = "../../modules/onboarding_role"
  trusted_role_arn = module.host.instance_role_arn
  external_id      = var.host_account_external_id
  tenant_name      = var.host_account_name
  role_name        = var.host_scan_role_name
}

output "instance_id" { value = module.host.instance_id }
output "instance_role_arn" { value = module.host.instance_role_arn }
output "self_scan_role_arn" { value = module.self_scan_role.role_arn }
output "shell_command" { value = module.host.shell_command }
output "dashboard_tunnel_command" { value = module.host.dashboard_tunnel_command }
