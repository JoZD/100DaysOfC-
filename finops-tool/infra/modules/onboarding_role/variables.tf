variable "trusted_role_arn" {
  description = "Explicit IAM role ARN of the scanner identity (set this or trusted_principal_arn_pattern)"
  type        = string
  default     = null
  validation {
    condition     = var.trusted_role_arn == null || can(regex("^arn:aws:iam::[0-9]{12}:role/[A-Za-z0-9_+=,.@/-]+$", var.trusted_role_arn))
    error_message = "trusted_role_arn must be an explicit IAM role ARN."
  }
}

variable "trusted_principal_arn_pattern" {
  description = "SSO scanner identity, as shown on the dashboard account page, e.g. arn:aws:iam::111111111111:role/aws-reserved/sso.amazonaws.com/*AWSReservedSSO_AdministratorAccess_0123456789abcdef"
  type        = string
  default     = null
  validation {
    condition     = var.trusted_principal_arn_pattern == null || can(regex("^arn:aws:iam::[0-9]{12}:role/aws-reserved/sso\\.amazonaws\\.com/\\*AWSReservedSSO_[A-Za-z0-9_+=,.@-]+$", var.trusted_principal_arn_pattern))
    error_message = "Expected arn:aws:iam::<account>:role/aws-reserved/sso.amazonaws.com/*AWSReservedSSO_<name>."
  }
}

variable "external_id" {
  description = "Unique per-account ExternalId required by every AssumeRole call"
  type        = string
  sensitive   = true
  validation {
    condition     = length(var.external_id) >= 16
    error_message = "Generate an ExternalId of at least 16 characters."
  }
}

variable "tenant_name" {
  description = "Account label used in the default role name"
  type        = string
}

variable "role_name" {
  description = "Optional explicit IAM role name (default FinOps-ReadOnly-<tenant_name>)"
  type        = string
  default     = null
  validation {
    condition     = var.role_name == null || startswith(coalesce(var.role_name, "x"), "FinOps-ReadOnly")
    error_message = "The role name must start with FinOps-ReadOnly (the scanner may assume only those)."
  }
}
