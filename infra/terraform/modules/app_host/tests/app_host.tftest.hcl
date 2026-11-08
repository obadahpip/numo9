# Offline tests for the app_host module (S-02-T02): mocked AWS provider, plan only.
# Run from modules/app_host:  tofu init && tofu test

mock_provider "aws" {
  mock_data "aws_ssm_parameter" {
    defaults = {
      value = "ami-0123456789abcdef0"
    }
  }

  mock_data "aws_iam_policy_document" {
    defaults = {
      json = "{\"Version\":\"2012-10-17\",\"Statement\":[]}"
    }
  }
}

variables {
  name                     = "numo9-test"
  vpc_id                   = "vpc-0123456789abcdef0"
  subnet_id                = "subnet-0123456789abcdef0"
  ssh_allowed_cidrs        = ["203.0.113.10/32", "198.51.100.0/24"]
  bootstrap_ssh_public_key = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAITestKeyOnlyForPlanTests test@numo9"
}

run "web_ports_open_to_internet" {
  command = plan

  assert {
    condition     = toset(keys(aws_vpc_security_group_ingress_rule.web)) == toset(["80", "443"])
    error_message = "Exactly ports 80 and 443 must be public."
  }

  assert {
    condition = alltrue([
      for r in values(aws_vpc_security_group_ingress_rule.web) :
      r.cidr_ipv4 == "0.0.0.0/0" && r.ip_protocol == "tcp" && r.from_port == r.to_port
    ])
    error_message = "Web rules must be single TCP ports open to 0.0.0.0/0."
  }
}

run "ssh_open_to_bastion_only" {
  command = plan

  assert {
    condition = toset([
      for r in values(aws_vpc_security_group_ingress_rule.ssh) : r.cidr_ipv4
    ]) == toset(["203.0.113.10/32", "198.51.100.0/24"])
    error_message = "Port 22 must be reachable only from ssh_allowed_cidrs."
  }

  assert {
    condition = alltrue([
      for r in values(aws_vpc_security_group_ingress_rule.ssh) :
      r.from_port == 22 && r.to_port == 22 && r.ip_protocol == "tcp"
    ])
    error_message = "SSH rules must be TCP 22 only."
  }

  assert {
    condition     = length(aws_vpc_security_group_ingress_rule.web) + length(aws_vpc_security_group_ingress_rule.ssh) == 4
    error_message = "No ingress rule other than 80, 443 and the two SSH sources may exist."
  }
}

run "host_baseline" {
  command = plan

  assert {
    condition     = aws_instance.host.metadata_options[0].http_tokens == "required"
    error_message = "IMDSv2 must be required."
  }

  assert {
    condition     = aws_instance.host.root_block_device[0].encrypted == true && aws_instance.host.root_block_device[0].volume_type == "gp3"
    error_message = "Root volume must be encrypted gp3."
  }

  assert {
    condition     = aws_instance.host.ami == "ami-0123456789abcdef0"
    error_message = "AMI must come from the Canonical SSM parameter."
  }

  assert {
    condition     = aws_iam_role_policy_attachment.ssm_core.policy_arn == "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
    error_message = "Instance role must allow Session Manager (break-glass path)."
  }

  assert {
    condition     = aws_eip.host.domain == "vpc"
    error_message = "Host must get a VPC Elastic IP for DNS."
  }
}

run "rejects_ssh_open_to_internet" {
  command = plan

  variables {
    ssh_allowed_cidrs = ["0.0.0.0/0"]
  }

  expect_failures = [var.ssh_allowed_cidrs]
}

run "rejects_wide_ssh_range" {
  command = plan

  variables {
    ssh_allowed_cidrs = ["10.0.0.0/16"]
  }

  expect_failures = [var.ssh_allowed_cidrs]
}

run "rejects_ipv6_ssh_range" {
  command = plan

  variables {
    ssh_allowed_cidrs = ["::/0"]
  }

  expect_failures = [var.ssh_allowed_cidrs]
}

run "rejects_empty_ssh_list" {
  command = plan

  variables {
    ssh_allowed_cidrs = []
  }

  expect_failures = [var.ssh_allowed_cidrs]
}

run "rejects_non_ed25519_key" {
  command = plan

  variables {
    bootstrap_ssh_public_key = "ssh-rsa AAAAB3NzaC1yc2E test"
  }

  expect_failures = [var.bootstrap_ssh_public_key]
}
