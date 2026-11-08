# Offline tests for the network module (S-02-T02): mocked AWS provider, plan only.
# Run from modules/network:  tofu init && tofu test

mock_provider "aws" {}

variables {
  name               = "numo9-test"
  cidr_block         = "10.20.0.0/16"
  availability_zones = ["ca-central-1a", "ca-central-1b"]
}

run "subnet_layout" {
  command = plan

  assert {
    condition     = [for s in aws_subnet.public : s.cidr_block] == ["10.20.0.0/20", "10.20.16.0/20"]
    error_message = "Public subnets must be the first two /20s."
  }

  assert {
    condition     = [for s in aws_subnet.private : s.cidr_block] == ["10.20.128.0/20", "10.20.144.0/20"]
    error_message = "Private subnets must be /20s in the upper half of the VPC."
  }

  assert {
    condition     = [for s in aws_subnet.public : s.availability_zone] == ["ca-central-1a", "ca-central-1b"]
    error_message = "One public subnet per availability zone."
  }

  assert {
    condition     = alltrue([for s in aws_subnet.public : s.map_public_ip_on_launch == false])
    error_message = "Public subnets must not auto-assign public IPs (hosts use Elastic IPs)."
  }
}

run "only_public_route_table_reaches_internet" {
  command = plan

  assert {
    condition     = aws_route.public_internet.destination_cidr_block == "0.0.0.0/0"
    error_message = "Public route table needs the default route to the internet gateway."
  }

  assert {
    condition     = length(aws_route_table.private.route) == 0
    error_message = "Private route table must have no route besides the implicit local one."
  }
}

run "default_security_group_locked" {
  command = plan

  assert {
    condition     = length(aws_default_security_group.this.ingress) == 0 && length(aws_default_security_group.this.egress) == 0
    error_message = "The VPC default security group must have no rules."
  }
}

run "rejects_one_availability_zone" {
  command = plan

  variables {
    availability_zones = ["ca-central-1a"]
  }

  expect_failures = [var.availability_zones]
}

run "rejects_oversized_vpc" {
  command = plan

  variables {
    cidr_block = "10.0.0.0/8"
  }

  expect_failures = [var.cidr_block]
}
