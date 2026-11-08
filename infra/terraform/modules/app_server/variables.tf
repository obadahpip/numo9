variable "name" {
  description = "Name prefix, e.g. numo9-staging."
  type        = string
}

variable "location" {
  description = "Hetzner location. ADR-0002: hel1 (Helsinki) for every workload."
  type        = string
  default     = "hel1"

  validation {
    condition     = var.location == "hel1"
    error_message = "ADR-0002: servers run in hel1 only (fsn1 is reserved for backup copies)."
  }
}

variable "server_type" {
  description = "Hetzner server type (x86; GHCR images are linux/amd64). Check orderability on the day."
  type        = string
  default     = "cpx32"

  validation {
    condition     = !startswith(var.server_type, "cax")
    error_message = "ARM (cax*) types cannot run the linux/amd64 images."
  }
}

variable "image" {
  description = "OS image."
  type        = string
  default     = "ubuntu-24.04"
}

variable "network_id" {
  description = "Private network the server joins."
  type        = string
}

variable "subnet_id" {
  description = "Subnet ID (dependency only: the server attaches after the subnet exists)."
  type        = string
}

variable "private_ip" {
  description = "Fixed private IP of the server inside the servers subnet."
  type        = string
  default     = "10.20.1.10"
}

variable "ssh_allowed_cidrs" {
  description = <<-EOT
    Bastion / admin source addresses allowed to reach port 22. Never the whole internet:
    each entry must be an IPv4 /24 or narrower.
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
  description = "ed25519 public key for the first root login, used once by Ansible (S-02-T05) to create named accounts and disable root login."
  type        = string

  validation {
    condition     = can(regex("^ssh-ed25519 [A-Za-z0-9+/=]+( .*)?$", var.bootstrap_ssh_public_key))
    error_message = "bootstrap_ssh_public_key must be an ssh-ed25519 public key."
  }
}

variable "protection" {
  description = "Delete/rebuild protection on server and primary IP (true for production)."
  type        = bool
  default     = false
}

variable "labels" {
  description = "Labels added to every resource."
  type        = map(string)
  default     = {}
}
