variable "name" {
  description = "Name prefix for every resource, e.g. numo9-staging."
  type        = string
}

variable "vpc_id" {
  description = "VPC the host and its security group belong to."
  type        = string
}

variable "subnet_id" {
  description = "Public subnet the host is launched in."
  type        = string
}

variable "instance_type" {
  description = "EC2 instance type (x86_64; GHCR images are built for linux/amd64)."
  type        = string
  default     = "t3.medium"
}

variable "root_volume_size_gb" {
  description = "Size of the encrypted gp3 root volume in GiB (Docker images, volumes, logs)."
  type        = number
  default     = 40

  validation {
    condition     = var.root_volume_size_gb >= 20 && var.root_volume_size_gb <= 500
    error_message = "root_volume_size_gb must be between 20 and 500."
  }
}

variable "ami_ssm_parameter" {
  description = "Public SSM parameter that resolves to the AMI (Canonical Ubuntu 24.04 LTS, amd64, gp3)."
  type        = string
  default     = "/aws/service/canonical/ubuntu/server/24.04/stable/current/amd64/hvm/ebs-gp3/ami-id"
}

variable "ssh_allowed_cidrs" {
  description = <<-EOT
    Bastion / admin source addresses allowed to reach port 22 (named GMA admin IPs or the bastion).
    Never the whole internet: each entry must be an IPv4 /24 or narrower.
  EOT
  type        = list(string)

  validation {
    condition     = length(var.ssh_allowed_cidrs) > 0
    error_message = "ssh_allowed_cidrs must list at least one bastion/admin address."
  }

  validation {
    condition = alltrue([
      for c in var.ssh_allowed_cidrs :
      can(cidrhost(c, 0)) && !strcontains(c, ":") && tonumber(split("/", c)[1]) >= 24
    ])
    error_message = "Each ssh_allowed_cidrs entry must be an IPv4 CIDR of /24 or narrower (0.0.0.0/0 is refused)."
  }
}

variable "bootstrap_ssh_public_key" {
  description = "Public key (ed25519) installed for the image's first login, used once by Ansible (S-02-T05) to create the named accounts."
  type        = string

  validation {
    condition     = can(regex("^ssh-ed25519 [A-Za-z0-9+/=]+( .*)?$", var.bootstrap_ssh_public_key))
    error_message = "bootstrap_ssh_public_key must be an ssh-ed25519 public key."
  }
}

variable "termination_protection" {
  description = "Refuse API termination of the instance (true for production)."
  type        = bool
  default     = false
}
