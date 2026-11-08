# Offline tests for the app_server module (S-02-T02): mocked hcloud provider, plan only.
# Run from modules/app_server:  tofu init && tofu test

mock_provider "hcloud" {
  # Hetzner IDs are numeric; the mock's random string IDs would fail type conversion.
  mock_resource "hcloud_network" {
    defaults = { id = "1001" }
  }
  mock_resource "hcloud_firewall" {
    defaults = { id = "2001" }
  }
  mock_resource "hcloud_ssh_key" {
    defaults = { id = "3001" }
  }
  mock_resource "hcloud_primary_ip" {
    defaults = { id = "4001", ip_address = "192.0.2.10" }
  }
  mock_resource "hcloud_server" {
    defaults = { id = "5001", ipv6_address = "2001:db8::1" }
  }
}

variables {
  name                     = "numo9-test"
  network_id               = "1001"
  subnet_id                = "1001-10.20.1.0/24"
  ssh_allowed_cidrs        = ["203.0.113.10/32", "198.51.100.0/24"]
  bootstrap_ssh_public_key = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAITestKeyOnlyForPlanTests test@numo9"
}

run "web_ports_public" {
  command = plan

  assert {
    condition = toset([
      for r in hcloud_firewall.server.rule : r.port if r.direction == "in" && r.protocol == "tcp" && contains(r.source_ips, "0.0.0.0/0")
    ]) == toset(["80", "443"])
    error_message = "Only TCP 80 and 443 may be open to the whole internet."
  }
}

run "ssh_bastion_only" {
  command = plan

  assert {
    condition = alltrue([
      for r in hcloud_firewall.server.rule :
      toset(r.source_ips) == toset(["203.0.113.10/32", "198.51.100.0/24"]) if r.port == "22"
    ])
    error_message = "Port 22 must be open only to ssh_allowed_cidrs."
  }

  assert {
    condition     = length([for r in hcloud_firewall.server.rule : r if r.port == "22"]) == 1
    error_message = "Exactly one SSH rule expected."
  }

  assert {
    condition     = length(hcloud_firewall.server.rule) == 4
    error_message = "Only 80, 443, 22 and ICMP rules may exist."
  }
}

run "server_in_helsinki_on_private_network" {
  command = plan

  assert {
    condition     = hcloud_server.this.location == "hel1" && hcloud_primary_ip.ipv4.location == "hel1"
    error_message = "Server and primary IP must be in hel1 (ADR-0002)."
  }

  assert {
    condition     = one(hcloud_server.this.network).ip == "10.20.1.10"
    error_message = "Server must join the private network with its fixed IP."
  }

  assert {
    condition     = hcloud_primary_ip.ipv4.auto_delete == false
    error_message = "Primary IP must survive server deletion (DNS stability)."
  }

  assert {
    condition     = hcloud_server.this.image == "ubuntu-24.04" && hcloud_server.this.server_type == "cpx32"
    error_message = "Defaults: Ubuntu 24.04 on cpx32."
  }
}

run "production_protection" {
  command = plan

  variables {
    protection = true
  }

  assert {
    condition     = hcloud_server.this.delete_protection && hcloud_server.this.rebuild_protection && hcloud_primary_ip.ipv4.delete_protection
    error_message = "protection=true must protect server and primary IP."
  }
}

run "rejects_location_outside_adr" {
  command = plan

  variables {
    location = "nbg1" # adr-0002: allow (negative test)
  }

  expect_failures = [var.location]
}

run "rejects_backup_location_for_workloads" {
  command = plan

  variables {
    location = "fsn1"
  }

  expect_failures = [var.location]
}

run "rejects_arm_server_type" {
  command = plan

  variables {
    server_type = "cax21"
  }

  expect_failures = [var.server_type]
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

run "rejects_ipv6_any" {
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
