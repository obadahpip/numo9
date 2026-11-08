# Offline tests for the staging stack (S-02-T02): mocked hcloud provider, plan only.
# Run from environments/staging:  tofu init -backend=false && tofu test

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
  hcloud_token             = "test-token-not-real"
  ssh_allowed_cidrs        = ["203.0.113.10/32"]
  bootstrap_ssh_public_key = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAITestKeyOnlyForPlanTests test@numo9"
}

run "staging_composes_in_helsinki" {
  command = plan

  assert {
    condition     = output.server_private_ip == "10.20.1.10"
    error_message = "App server must sit at 10.20.1.10 on the private network."
  }

  assert {
    condition     = module.network.servers_subnet == "10.20.1.0/24"
    error_message = "Staging servers subnet must be 10.20.1.0/24."
  }
}
