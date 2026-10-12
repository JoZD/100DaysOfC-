variable "name" {
  description = "Name prefix for every resource"
  type        = string
  default     = "finops"
}

variable "vpc_id" {
  description = "VPC for the server"
  type        = string
}

variable "subnet_id" {
  description = <<-EOT
    Subnet for the server. It needs OUTBOUND internet (NAT gateway, or a public
    subnet with associate_public_ip = true) to reach AWS APIs and
    package registries. No inbound access is ever opened.
  EOT
  type        = string
}

variable "associate_public_ip" {
  description = "true only for a public subnet without NAT (still no inbound rules)"
  type        = bool
  default     = false
}

variable "instance_type" {
  description = "4 GB RAM is enough to build the images on the box and run the stack"
  type        = string
  default     = "t3.medium"
}

variable "root_volume_gb" {
  description = "Root volume (OS + Docker images + Postgres data)"
  type        = number
  default     = 40
}

variable "snapshot_retention_days" {
  description = "Daily EBS snapshots of the server disk (includes the database) kept for this many days"
  type        = number
  default     = 14
}
