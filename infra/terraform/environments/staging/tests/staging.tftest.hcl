# Offline tests for the staging stack (S-02-T02): mocked AWS provider, plan only.
# Run from environments/staging:  tofu init -backend=false && tofu test
# Module behaviour (firewall, subnets) is tested in modules/*/tests.

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
  ssh_allowed_cidrs        = ["203.0.113.10/32"]
  bootstrap_ssh_public_key = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAITestKeyOnlyForPlanTests test@numo9"
}

run "plans_in_canada_central" {
  command = plan

  assert {
    condition     = var.region == "ca-central-1"
    error_message = "Default region must be ca-central-1 (ADR-0001)."
  }

  assert {
    condition     = alltrue([for az in var.availability_zones : startswith(az, "ca-central-1")])
    error_message = "Every availability zone must belong to ca-central-1."
  }

  assert {
    condition     = length(output.public_subnet_ids) == 2 && length(output.private_subnet_ids) == 2
    error_message = "Staging needs two public and two private subnets."
  }
}

run "rejects_region_outside_adr" {
  command = plan

  variables {
    region = "us-east-1" # adr-0001: allow (negative test)
  }

  expect_failures = [var.region]
}

run "rejects_backup_region_for_workloads" {
  command = plan

  variables {
    region = "ca-west-1"
  }

  expect_failures = [var.region]
}
