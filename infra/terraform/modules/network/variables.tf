variable "name" {
  description = "Name prefix for every resource, e.g. numo9-staging."
  type        = string
}

variable "cidr_block" {
  description = "IPv4 CIDR of the VPC (a /16 to /24 private range)."
  type        = string

  validation {
    condition     = can(cidrhost(var.cidr_block, 0)) && tonumber(split("/", var.cidr_block)[1]) >= 16 && tonumber(split("/", var.cidr_block)[1]) <= 24
    error_message = "cidr_block must be a valid IPv4 CIDR between /16 and /24."
  }
}

variable "availability_zones" {
  description = "Exactly two availability zones of the region (one public + one private subnet each)."
  type        = list(string)

  validation {
    condition     = length(var.availability_zones) == 2
    error_message = "Exactly two availability zones are required (RDS subnet groups need two, S-02-T04)."
  }
}
