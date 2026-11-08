output "network_id" {
  description = "ID of the private network."
  value       = hcloud_network.this.id
}

output "ip_range" {
  description = "Private range of the network."
  value       = hcloud_network.this.ip_range
}

output "servers_subnet" {
  description = "Subnet for cloud servers."
  value       = hcloud_network_subnet.servers.ip_range
}

output "subnet_id" {
  description = "ID of the servers subnet (servers attach after it exists)."
  value       = hcloud_network_subnet.servers.id
}
