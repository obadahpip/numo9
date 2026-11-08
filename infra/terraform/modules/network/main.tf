# Network for one environment (S-02-T02, ADR-0001).
#   - 2 public subnets  : app host(s) with a public Elastic IP behind the security group
#   - 2 private subnets : no internet route; reserved for RDS PostgreSQL (S-02-T04)
# No NAT gateway: nothing in the private subnets needs outbound internet access.

locals {
  # /16 -> /20 subnets; public = netnum 0,1 ; private = netnum 8,9
  public_cidrs  = [for i, _ in var.availability_zones : cidrsubnet(var.cidr_block, 4, i)]
  private_cidrs = [for i, _ in var.availability_zones : cidrsubnet(var.cidr_block, 4, i + 8)]
}

resource "aws_vpc" "this" {
  cidr_block           = var.cidr_block
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = { Name = var.name }
}

# The VPC's default security group allows all traffic between members; strip every rule so
# nothing can use it by accident (CIS AWS 5.4).
resource "aws_default_security_group" "this" {
  vpc_id = aws_vpc.this.id
  tags   = { Name = "${var.name}-default-locked" }
}

resource "aws_internet_gateway" "this" {
  vpc_id = aws_vpc.this.id
  tags   = { Name = var.name }
}

resource "aws_subnet" "public" {
  count = length(var.availability_zones)

  vpc_id                  = aws_vpc.this.id
  availability_zone       = var.availability_zones[count.index]
  cidr_block              = local.public_cidrs[count.index]
  map_public_ip_on_launch = false # hosts get an explicit Elastic IP instead

  tags = { Name = "${var.name}-public-${var.availability_zones[count.index]}", Tier = "public" }
}

resource "aws_subnet" "private" {
  count = length(var.availability_zones)

  vpc_id            = aws_vpc.this.id
  availability_zone = var.availability_zones[count.index]
  cidr_block        = local.private_cidrs[count.index]

  tags = { Name = "${var.name}-private-${var.availability_zones[count.index]}", Tier = "private" }
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.this.id
  tags   = { Name = "${var.name}-public" }
}

resource "aws_route" "public_internet" {
  route_table_id         = aws_route_table.public.id
  destination_cidr_block = "0.0.0.0/0"
  gateway_id             = aws_internet_gateway.this.id
}

resource "aws_route_table_association" "public" {
  count = length(aws_subnet.public)

  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}

# Private route table: local VPC route only (no internet route on purpose).
resource "aws_route_table" "private" {
  vpc_id = aws_vpc.this.id
  tags   = { Name = "${var.name}-private" }
}

resource "aws_route_table_association" "private" {
  count = length(aws_subnet.private)

  subnet_id      = aws_subnet.private[count.index].id
  route_table_id = aws_route_table.private.id
}
