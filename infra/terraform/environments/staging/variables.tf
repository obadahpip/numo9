variable "region" {
  description = "AWS region. ADR-0001 allows only ca-central-1 for workloads."
  type        = string
  default     = "ca-central-1"

  validation {
    condition     = var.region == "ca-central-1"
    error_message = "ADR-0001: staging runs in ca-central-1 only (ca-west-1 is reserved for backup copies)."
  }
}

variable "allowed_account_ids" {
  description = "AWS account IDs this stack may touch (guards against applying to the wrong account). Empty = no guard."
  type        = list(string)
  default     = []
}

variable "vpc_cidr" {
  description = "IPv4 CIDR of the staging VPC."
  type        = string
  default     = "10.20.0.0/16"
}

variable "availability_zones" {
  description = "Two availability zones in ca-central-1."
  type        = list(string)
  default     = ["ca-central-1a", "ca-central-1b"]
}

variable "instance_type" {
  description = "Staging host instance type."
  type        = string
  default     = "t3.medium"
}

variable "root_volume_size_gb" {
  description = "Staging host root volume (GiB)."
  type        = number
  default     = 40
}

variable "ssh_allowed_cidrs" {
  description = "Bastion / named admin IPv4 CIDRs allowed to reach port 22 (each /24 or narrower)."
  type        = list(string)
}

variable "bootstrap_ssh_public_key" {
  description = "ed25519 public key for the first login (used by Ansible, S-02-T05)."
  type        = string
}
