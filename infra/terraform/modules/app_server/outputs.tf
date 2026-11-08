output "server_id" {
  description = "Hetzner server ID."
  value       = hcloud_server.this.id
}

output "public_ipv4" {
  description = "Primary IPv4 — STAGING_SSH_HOST and DNS A records (S-02-T07)."
  value       = hcloud_primary_ip.ipv4.ip_address
}

output "public_ipv6" {
  description = "IPv6 address of the server (DNS AAAA records, S-02-T07)."
  value       = hcloud_server.this.ipv6_address
}

output "private_ip" {
  description = "Private IP on the environment network."
  value       = var.private_ip
}

output "firewall_id" {
  description = "Hetzner Cloud Firewall ID."
  value       = hcloud_firewall.server.id
}
