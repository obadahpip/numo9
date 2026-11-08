output "server_public_ipv4" {
  description = "Primary IPv4 — GitHub STAGING_SSH_HOST and DNS A records (S-02-T07)."
  value       = module.server.public_ipv4
}

output "server_public_ipv6" {
  description = "Server IPv6 — DNS AAAA records (S-02-T07)."
  value       = module.server.public_ipv6
}

output "server_private_ip" {
  description = "Private IP of the app server (PostgreSQL listens here only, S-02-T04)."
  value       = module.server.private_ip
}

output "network_id" {
  description = "Private network ID (PostgreSQL server/volume in S-02-T04)."
  value       = module.network.network_id
}

output "firewall_id" {
  description = "Cloud Firewall ID."
  value       = module.server.firewall_id
}
