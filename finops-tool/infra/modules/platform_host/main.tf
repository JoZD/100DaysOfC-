# The FinOps Tool server: one EC2 instance running the docker-compose stack
# (Postgres + API + scanner + web). Lives in a company AWS account; nothing
# about it is reachable from the network — operators and dashboard users come
# in through SSM Session Manager.

data "aws_ssm_parameter" "ubuntu_ami" {
  # Ubuntu 24.04 LTS: SSM agent preinstalled; docker.io + docker-compose-v2 in apt.
  name = "/aws/service/canonical/ubuntu/server/24.04/stable/current/amd64/hvm/ebs-gp3/ami-id"
}

# ---------------------------------------------------------------- IAM ------

data "aws_iam_policy_document" "ec2_trust" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "host" {
  name               = "${var.name}-host"
  assume_role_policy = data.aws_iam_policy_document.ec2_trust.json
}

# Session Manager: shell access and port-forwarding without SSH or open ports.
resource "aws_iam_role_policy_attachment" "ssm" {
  role       = aws_iam_role.host.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

# The ONLY thing the scanner can do with its own identity: assume roles named
# FinOps-ReadOnly* (any account). Each target role trusts this exact role ARN and
# requires its account's ExternalId. Must match aws_access.SOURCE_ASSUME_RESOURCE.
data "aws_iam_policy_document" "assume_scan_roles" {
  statement {
    sid       = "AssumeFinOpsTargetRoles"
    actions   = ["sts:AssumeRole"]
    resources = ["arn:aws:iam::*:role/FinOps-ReadOnly*"]
  }
}

resource "aws_iam_role_policy" "assume_scan_roles" {
  name   = "assume-finops-readonly-roles"
  role   = aws_iam_role.host.id
  policy = data.aws_iam_policy_document.assume_scan_roles.json
}

resource "aws_iam_instance_profile" "host" {
  name = "${var.name}-host"
  role = aws_iam_role.host.name
}

# ------------------------------------------------------------ network ------

resource "aws_security_group" "host" {
  name        = "${var.name}-host"
  description = "FinOps Tool server: no inbound; outbound HTTP(S) only"
  vpc_id      = var.vpc_id

  # AWS cannot edit a security group's description in place. A branding-only
  # change must not replace an existing host's security group.
  lifecycle {
    ignore_changes = [description]
  }

  egress {
    description = "AWS APIs, container/package registries"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    description = "apt mirrors"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# ----------------------------------------------------------- instance ------

resource "aws_instance" "host" {
  ami                         = data.aws_ssm_parameter.ubuntu_ami.value
  instance_type               = var.instance_type
  subnet_id                   = var.subnet_id
  vpc_security_group_ids      = [aws_security_group.host.id]
  iam_instance_profile        = aws_iam_instance_profile.host.name
  associate_public_ip_address = var.associate_public_ip
  disable_api_termination     = true
  user_data                   = file("${path.module}/user_data.sh")

  metadata_options {
    http_tokens = "required" # IMDSv2 only
    # 2 hops: containers sit one network hop behind the host and must reach
    # IMDS to pick up the instance role credentials.
    http_put_response_hop_limit = 2
  }

  root_block_device {
    volume_type = "gp3"
    volume_size = var.root_volume_gb
    encrypted   = true
  }

  tags = {
    Name            = var.name
    FinOpsSnapshots = "daily"
  }

  lifecycle {
    ignore_changes = [ami] # don't replace the server (and its DB) on every new AMI
  }
}

# ------------------------------------------------------------ backups ------

data "aws_iam_policy_document" "dlm_trust" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["dlm.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "dlm" {
  name               = "${var.name}-dlm"
  assume_role_policy = data.aws_iam_policy_document.dlm_trust.json
}

resource "aws_iam_role_policy_attachment" "dlm" {
  role       = aws_iam_role.dlm.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSDataLifecycleManagerServiceRole"
}

resource "aws_dlm_lifecycle_policy" "daily" {
  description        = "${var.name} daily disk snapshots"
  execution_role_arn = aws_iam_role.dlm.arn
  state              = "ENABLED"

  policy_details {
    resource_types = ["INSTANCE"]
    target_tags = {
      FinOpsSnapshots = "daily"
    }

    schedule {
      name      = "daily"
      copy_tags = true
      create_rule {
        interval      = 24
        interval_unit = "HOURS"
        times         = ["05:00"]
      }
      retain_rule {
        count = var.snapshot_retention_days
      }
    }
  }
}
