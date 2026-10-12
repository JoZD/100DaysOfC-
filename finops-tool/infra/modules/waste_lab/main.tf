# Deliberately wasteful, cheap resources in ONE region of a test account, so a
# real FinOps Tool scan has something to find. Create, scan, destroy.
#
# Positive cases (each rule must flag them):
#   - unattached EBS volumes      -> orphaned_ebs_volumes
#   - Elastic IPs not associated  -> unassociated_eips
# Negative controls (must NOT be flagged):
#   - an Elastic IP associated with a detached network interface

terraform {
  required_providers {
    aws = {
      source = "hashicorp/aws"
    }
  }
}

data "aws_region" "current" {}

data "aws_availability_zones" "available" {
  state = "available"
}

locals {
  region = data.aws_region.current.name
  az     = data.aws_availability_zones.available.names[0]
  # Must mirror rules/catalog/orphaned_ebs_volumes.yaml.
  ebs_price_per_gb = { gp3 = 0.08, gp2 = 0.10, io1 = 0.125, io2 = 0.125 }
  # Must mirror rules/catalog/unassociated_eips.yaml.
  eip_monthly_usd = 3.6
}

resource "aws_ebs_volume" "orphan" {
  count             = length(var.orphan_volumes)
  availability_zone = local.az
  type              = var.orphan_volumes[count.index].type
  size              = var.orphan_volumes[count.index].size_gb
  encrypted         = true

  tags = {
    Name     = "${var.lab_name}-orphan-${count.index}"
    LabCase  = "orphaned_ebs_volumes"
    Expected = "finding"
  }
}

resource "aws_eip" "unassociated" {
  count  = var.unassociated_eips
  domain = "vpc"

  tags = {
    Name     = "${var.lab_name}-unassociated-${count.index}"
    LabCase  = "unassociated_eips"
    Expected = "finding"
  }
}

# --- Negative control: an associated EIP (needs the default VPC) -------------

data "aws_vpc" "default" {
  count   = var.create_controls ? 1 : 0
  default = true
}

data "aws_subnets" "default" {
  count = var.create_controls ? 1 : 0
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default[0].id]
  }
  filter {
    name   = "availability-zone"
    values = [local.az]
  }
}

resource "aws_network_interface" "control" {
  count     = var.create_controls ? 1 : 0
  subnet_id = data.aws_subnets.default[0].ids[0]

  tags = {
    Name     = "${var.lab_name}-control-eni"
    LabCase  = "unassociated_eips"
    Expected = "no-finding"
  }
}

resource "aws_eip" "associated_control" {
  count  = var.create_controls ? 1 : 0
  domain = "vpc"

  tags = {
    Name     = "${var.lab_name}-associated-control"
    LabCase  = "unassociated_eips"
    Expected = "no-finding"
  }
}

resource "aws_eip_association" "control" {
  count                = var.create_controls ? 1 : 0
  allocation_id        = aws_eip.associated_control[0].id
  network_interface_id = aws_network_interface.control[0].id
}
