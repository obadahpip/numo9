output "vpc_id" {
  description = "Staging VPC ID."
  value       = module.network.vpc_id
}

output "public_subnet_ids" {
  description = "Public subnets (app hosts)."
  value       = module.network.public_subnet_ids
}

output "private_subnet_ids" {
  description = "Private subnets without internet route (RDS, S-02-T04)."
  value       = module.network.private_subnet_ids
}

output "host_public_ip" {
  description = "Staging host Elastic IP — STAGING_SSH_HOST and DNS A records (S-02-T07)."
  value       = module.host.public_ip
}

output "host_instance_id" {
  description = "Staging host instance ID."
  value       = module.host.instance_id
}

output "host_security_group_id" {
  description = "Staging host security group."
  value       = module.host.security_group_id
}

output "host_iam_role_name" {
  description = "Staging host instance role."
  value       = module.host.iam_role_name
}
