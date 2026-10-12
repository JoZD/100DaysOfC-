output "expected_findings" {
  description = "Findings a scan of this region must produce"
  value = concat(
    [for v in aws_ebs_volume.orphan : {
      rule_id             = "orphaned_ebs_volumes"
      resource_id         = v.id
      region              = local.region
      monthly_savings_usd = v.size * lookup(local.ebs_price_per_gb, v.type, 0.10)
    }],
    [for e in aws_eip.unassociated : {
      rule_id             = "unassociated_eips"
      resource_id         = e.allocation_id
      region              = local.region
      monthly_savings_usd = local.eip_monthly_usd
    }],
  )
}

output "controls" {
  description = "Resource IDs a scan must NOT flag"
  value = [for e in aws_eip.associated_control : {
    rule_id     = "unassociated_eips"
    resource_id = e.allocation_id
    region      = local.region
  }]
}
