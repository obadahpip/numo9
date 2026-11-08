# One application server: Docker Compose stack behind Caddy (S-02-T02, ADR-0002).
# Hetzner Cloud Firewall (inbound; everything not listed is dropped):
#   80/tcp, 443/tcp  <- internet (Caddy: HTTP->HTTPS redirect, ACME, TLS)
#   22/tcp           <- var.ssh_allowed_cidrs only (bastion / named admin IPs)
#   ICMP             <- internet (path MTU discovery, diagnostics)
# Outbound is unrestricted (GHCR pulls, OS updates, Object Storage, ACME).
# Host hardening (ufw, fail2ban, named accounts, auditd, root login off) is S-02-T05 (Ansible).

resource "hcloud_firewall" "server" {
  name   = "${var.name}-server"
  labels = var.labels

  rule {
    description = "HTTP (Caddy redirect + ACME)"
    direction   = "in"
    protocol    = "tcp"
    port        = "80"
    source_ips  = ["0.0.0.0/0", "::/0"]
  }

  rule {
    description = "HTTPS (Caddy)"
    direction   = "in"
    protocol    = "tcp"
    port        = "443"
    source_ips  = ["0.0.0.0/0", "::/0"]
  }

  rule {
    description = "SSH from bastion/admin IPs only"
    direction   = "in"
    protocol    = "tcp"
    port        = "22"
    source_ips  = var.ssh_allowed_cidrs
  }

  rule {
    description = "ICMP"
    direction   = "in"
    protocol    = "icmp"
    source_ips  = ["0.0.0.0/0", "::/0"]
  }
}

resource "hcloud_ssh_key" "bootstrap" {
  name       = "${var.name}-bootstrap"
  public_key = var.bootstrap_ssh_public_key
  labels     = var.labels
}

# Primary IP kept separately from the server so DNS (S-02-T07) survives a server rebuild.
resource "hcloud_primary_ip" "ipv4" {
  name              = "${var.name}-ipv4"
  type              = "ipv4"
  location          = var.location
  auto_delete       = false
  delete_protection = var.protection
  labels            = var.labels
}

resource "hcloud_server" "this" {
  name                     = "${var.name}-app"
  server_type              = var.server_type
  image                    = var.image
  location                 = var.location
  ssh_keys                 = [hcloud_ssh_key.bootstrap.id]
  firewall_ids             = [hcloud_firewall.server.id]
  delete_protection        = var.protection
  rebuild_protection       = var.protection
  shutdown_before_deletion = true
  labels                   = var.labels

  public_net {
    ipv4_enabled = true
    ipv4         = hcloud_primary_ip.ipv4.id
    ipv6_enabled = true
  }

  network {
    network_id = var.network_id
    ip         = var.private_ip
  }

  # The server may only attach once the subnet exists.
  depends_on = [terraform_data.subnet_ready]

  lifecycle {
    # A new image version must not silently rebuild a running server.
    ignore_changes = [image, ssh_keys]
  }
}

resource "terraform_data" "subnet_ready" {
  input = var.subnet_id
}
