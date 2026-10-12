output "instance_id" {
  value = aws_instance.host.id
}

output "instance_role_arn" {
  description = "Pass this as trusted_role_arn to every onboarding_role deployment"
  value       = aws_iam_role.host.arn
}

output "dashboard_tunnel_command" {
  description = "Run on your workstation, then open http://localhost:3000"
  value       = "aws ssm start-session --target ${aws_instance.host.id} --document-name AWS-StartPortForwardingSession --parameters '{\"portNumber\":[\"3000\"],\"localPortNumber\":[\"3000\"]}'"
}

output "shell_command" {
  value = "aws ssm start-session --target ${aws_instance.host.id}"
}
