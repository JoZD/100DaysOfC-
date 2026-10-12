# Deployed into EVERY AWS account FinOps Tool scans (including the host account
# itself). Read-only, ExternalId-gated, trusted only by the FinOps Tool server.

locals {
  # SSO (IAM Identity Center) roles live under a path STS does not report, so
  # they are trusted as: account principal + ArnLike on aws:PrincipalArn.
  sso_account_id = var.trusted_principal_arn_pattern == null ? null : split(":", var.trusted_principal_arn_pattern)[4]
}

data "aws_iam_policy_document" "trust" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type = "AWS"
      identifiers = [
        var.trusted_role_arn != null ? var.trusted_role_arn : "arn:aws:iam::${local.sso_account_id}:root"
      ]
    }

    condition {
      test     = "StringEquals"
      variable = "sts:ExternalId"
      values   = [var.external_id]
    }

    dynamic "condition" {
      for_each = var.trusted_principal_arn_pattern == null ? [] : [var.trusted_principal_arn_pattern]
      content {
        test     = "ArnLike"
        variable = "aws:PrincipalArn"
        values   = [condition.value]
      }
    }
  }
}

data "aws_iam_policy_document" "readonly" {
  # Exact APIs called by the current production inventory collector.
  statement {
    sid = "FinOpsInventoryReadOnly"
    actions = [
      "ec2:DescribeRegions",
      "ec2:DescribeVolumes",
      "ec2:DescribeAddresses",
    ]
    resources = ["*"]
  }
}

resource "aws_iam_role" "readonly" {
  name                 = var.role_name != null ? var.role_name : "FinOps-ReadOnly-${var.tenant_name}"
  assume_role_policy   = data.aws_iam_policy_document.trust.json
  max_session_duration = 3600

  lifecycle {
    precondition {
      condition     = (var.trusted_role_arn == null) != (var.trusted_principal_arn_pattern == null)
      error_message = "Set exactly one of trusted_role_arn or trusted_principal_arn_pattern."
    }
  }
}

resource "aws_iam_role_policy" "readonly" {
  name   = "finops-readonly-policy"
  role   = aws_iam_role.readonly.id
  policy = data.aws_iam_policy_document.readonly.json
}
