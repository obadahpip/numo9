terraform {
  # OpenTofu is the reference tool (the plan allows "Terraform (or OpenTofu)"); the
  # configuration is also valid for Terraform >= 1.10.
  required_version = ">= 1.10.0"

  required_providers {
    hcloud = {
      source  = "hetznercloud/hcloud"
      version = "~> 1.70"
    }
  }

  # Remote state in Hetzner Object Storage, hel1 (S3-compatible). Settings at init time:
  #   tofu init -backend-config=backend.hcl        (see backend.hcl.example)
  backend "s3" {}
}
