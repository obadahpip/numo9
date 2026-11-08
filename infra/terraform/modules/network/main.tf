# Private network for one environment (S-02-T02, ADR-0002).
# The app server and the self-hosted PostgreSQL (S-02-T04) talk over this network; PostgreSQL is
# never exposed on a public interface.

locals {
  # Second /24 of the range (netnum 1) for cloud servers, e.g. 10.20.1.0/24.
  servers_subnet = cidrsubnet(var.ip_range, 24 - tonumber(split("/", var.ip_range)[1]), 1)
}

resource "hcloud_network" "this" {
  name     = var.name
  ip_range = var.ip_range
  labels   = var.labels
}

resource "hcloud_network_subnet" "servers" {
  network_id   = hcloud_network.this.id
  type         = "cloud"
  network_zone = var.network_zone
  ip_range     = local.servers_subnet
}
