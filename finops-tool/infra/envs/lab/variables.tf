variable "aws_profile" {
  description = "AWS CLI profile with rights to create EC2/EBS resources in the test account"
  type        = string
  default     = null
}

variable "expected_account_id" {
  description = "Guard: the 12-digit test account the profile must resolve to"
  type        = string
  validation {
    condition     = can(regex("^[0-9]{12}$", var.expected_account_id))
    error_message = "expected_account_id must be a 12-digit AWS account ID."
  }
}

variable "region" {
  description = "Region for the lab resources"
  type        = string
  default     = "us-east-1"
}

variable "secondary_region" {
  description = "Optional second region with one orphan volume (tests region discovery)"
  type        = string
  default     = null
}

variable "lab_name" {
  description = "Prefix for Name tags; also the Lab tag"
  type        = string
  default     = "finops-lab"
}

variable "orphan_volumes" {
  description = "Unattached EBS volumes in the primary region"
  type = list(object({
    type    = string
    size_gb = number
  }))
  default = [
    { type = "gp3", size_gb = 1 },
    { type = "gp2", size_gb = 1 },
  ]
}

variable "unassociated_eips" {
  description = "Unassociated Elastic IPs in the primary region"
  type        = number
  default     = 1
}

variable "create_controls" {
  description = "Associated EIP negative control (needs the default VPC in the primary region)"
  type        = bool
  default     = true
}
