terraform {
  # OpenTofu is the reference tool (the plan allows "Terraform (or OpenTofu)"); the
  # configuration is also valid for Terraform >= 1.10.
  required_version = ">= 1.10.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.70"
    }
  }

  # Remote state in ca-central-1 (bucket created by ../bootstrap). Settings are supplied at
  # init time:  tofu init -backend-config=backend.hcl   (see backend.hcl.example)
  backend "s3" {}
}
