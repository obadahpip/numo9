output "instance_id" {
  description = "EC2 instance ID."
  value       = aws_instance.host.id
}

output "public_ip" {
  description = "Elastic IP of the host (DNS A records, S-02-T07; STAGING_SSH_HOST)."
  value       = aws_eip.host.public_ip
}

output "private_ip" {
  description = "Private IP inside the VPC."
  value       = aws_instance.host.private_ip
}

output "security_group_id" {
  description = "Security group of the host (RDS ingress source in S-02-T04)."
  value       = aws_security_group.host.id
}

output "iam_role_name" {
  description = "Instance role (S3 bucket access added in S-02-T03)."
  value       = aws_iam_role.host.name
}
