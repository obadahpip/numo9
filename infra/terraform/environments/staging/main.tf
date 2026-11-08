# Numo9 staging on Hetzner Cloud, Helsinki (S-02-T02, ADR-0002): private network, app server,
# primary IPv4 and Cloud Firewall. Production reuses the same modules with protection = true.

locals {
  name = "numo9-staging"
  labels = {
    project     = "numo9"
    environment = "staging"
    managed-by  = "opentofu"
    residency   = "eu-fi"
  }
}

provider "hcloud" {
  token = var.hcloud_token
}

module "network" {
  source = "../../modules/network"

  name     = local.name
  ip_range = "10.20.0.0/16"
  labels   = local.labels
}

module "server" {
  source = "../../modules/app_server"

  name                     = local.name
  location                 = "hel1"
  server_type              = var.server_type
  network_id               = module.network.network_id
  subnet_id                = module.network.subnet_id
  private_ip               = "10.20.1.10"
  ssh_allowed_cidrs        = var.ssh_allowed_cidrs
  bootstrap_ssh_public_key = var.bootstrap_ssh_public_key
  protection               = false
  labels                   = local.labels
}
