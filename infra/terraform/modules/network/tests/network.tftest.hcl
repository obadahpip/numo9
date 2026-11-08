# Offline tests for the network module (S-02-T02): mocked hcloud provider, plan only.
# Run from modules/network:  tofu init && tofu test

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
  name = "numo9-test"
}

run "private_network_layout" {
  command = plan

  assert {
    condition     = hcloud_network.this.ip_range == "10.20.0.0/16"
    error_message = "Default private range must be 10.20.0.0/16."
  }

  assert {
    condition     = hcloud_network_subnet.servers.ip_range == "10.20.1.0/24"
    error_message = "Servers subnet must be 10.20.1.0/24."
  }

  assert {
    condition     = hcloud_network_subnet.servers.network_zone == "eu-central" && hcloud_network_subnet.servers.type == "cloud"
    error_message = "Subnet must be a cloud subnet in eu-central."
  }
}

run "small_range_still_gets_a_subnet" {
  command = plan

  variables {
    ip_range = "10.30.0.0/23"
  }

  assert {
    condition     = hcloud_network_subnet.servers.ip_range == "10.30.1.0/24"
    error_message = "A /23 network must yield the second /24 as the servers subnet."
  }
}

run "rejects_other_network_zone" {
  command = plan

  variables {
    network_zone = "us-east" # adr-0002: allow (negative test)
  }

  expect_failures = [var.network_zone]
}

run "rejects_oversized_range" {
  command = plan

  variables {
    ip_range = "10.0.0.0/8"
  }

  expect_failures = [var.ip_range]
}
