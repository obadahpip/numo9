variable "name" {
  description = "Name prefix, e.g. numo9-staging."
  type        = string
}

variable "ip_range" {
  description = "Private IPv4 range of the network (/16 to /23; the servers subnet is its second /24)."
  type        = string
  default     = "10.20.0.0/16"

  validation {
    condition     = can(cidrhost(var.ip_range, 0)) && tonumber(split("/", var.ip_range)[1]) >= 16 && tonumber(split("/", var.ip_range)[1]) <= 23
    error_message = "ip_range must be a valid IPv4 CIDR between /16 and /23."
  }
}

variable "network_zone" {
  description = "Hetzner network zone. ADR-0002: eu-central (contains hel1 and fsn1)."
  type        = string
  default     = "eu-central"

  validation {
    condition     = var.network_zone == "eu-central"
    error_message = "ADR-0002: the network zone must be eu-central."
  }
}

variable "labels" {
  description = "Labels added to every resource."
  type        = map(string)
  default     = {}
}
