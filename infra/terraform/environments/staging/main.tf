# Numo9 staging — network, host and firewall (S-02-T02). Region and residency: ADR-0001.

locals {
  name = "numo9-staging"
}

provider "aws" {
  region              = var.region
  allowed_account_ids = length(var.allowed_account_ids) > 0 ? var.allowed_account_ids : null

  default_tags {
    tags = {
      Project       = "numo9"
      Environment   = "staging"
      ManagedBy     = "opentofu"
      DataResidency = "CA"
      Source        = "infra/terraform/environments/staging"
    }
  }
}

module "network" {
  source = "../../modules/network"

  name               = local.name
  cidr_block         = var.vpc_cidr
  availability_zones = var.availability_zones
}

module "host" {
  source = "../../modules/app_host"

  name                     = local.name
  vpc_id                   = module.network.vpc_id
  subnet_id                = module.network.public_subnet_ids[0]
  instance_type            = var.instance_type
  root_volume_size_gb      = var.root_volume_size_gb
  ssh_allowed_cidrs        = var.ssh_allowed_cidrs
  bootstrap_ssh_public_key = var.bootstrap_ssh_public_key
  termination_protection   = false
}
