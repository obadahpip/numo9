variable "hcloud_token" {
  description = "Hetzner Cloud API token (project-scoped, read/write). Pass via TF_VAR_hcloud_token; never commit."
  type        = string
  sensitive   = true
}

variable "server_type" {
  description = "Server type for the app server."
  type        = string
  default     = "cpx32"
}

variable "ssh_allowed_cidrs" {
  description = "Bastion / named admin IPv4 CIDRs allowed to reach port 22 (each /24 or narrower)."
  type        = list(string)
}

variable "bootstrap_ssh_public_key" {
  description = "ed25519 public key for the first login (used by Ansible, S-02-T05)."
  type        = string
}
