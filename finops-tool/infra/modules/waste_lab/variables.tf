variable "lab_name" {
  description = "Prefix for resource Name tags"
  type        = string
}

variable "orphan_volumes" {
  description = "Unattached EBS volumes to create (1 GiB gp3 costs about $0.08/month)"
  type = list(object({
    type    = string
    size_gb = number
  }))
  default = [
    { type = "gp3", size_gb = 1 },
    { type = "gp2", size_gb = 1 },
  ]
  validation {
    condition     = alltrue([for v in var.orphan_volumes : contains(["gp3", "gp2"], v.type) && v.size_gb >= 1 && v.size_gb <= 10])
    error_message = "Use gp3/gp2 volumes of 1-10 GiB (st1/sc1 have a 125 GiB minimum, io1/io2 bill IOPS)."
  }
}

variable "unassociated_eips" {
  description = "Elastic IPs left unassociated (about $0.005/hour each)"
  type        = number
  default     = 1
}

variable "create_controls" {
  description = "Also create an associated EIP that must NOT be flagged (needs a default VPC)"
  type        = bool
  default     = true
}
