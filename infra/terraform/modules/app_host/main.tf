# One application host: Docker Compose stack behind Caddy (S-02-T02, ADR-0001).
# Firewall (security group):
#   80/tcp, 443/tcp  <- internet (Caddy: HTTP->HTTPS redirect and TLS)
#   22/tcp           <- var.ssh_allowed_cidrs only (bastion / named admin IPs)
#   all other ingress refused; egress open (GHCR pulls, OS updates, Let's Encrypt).
# Host hardening (fail2ban, named accounts, auditd, ufw) is S-02-T05 (Ansible).

data "aws_ssm_parameter" "ami" {
  name = var.ami_ssm_parameter
}

resource "aws_security_group" "host" {
  name_prefix = "${var.name}-host-"
  description = "Numo9 app host: 80/443 public, 22 bastion only"
  vpc_id      = var.vpc_id

  tags = { Name = "${var.name}-host" }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_vpc_security_group_ingress_rule" "web" {
  for_each = toset(["80", "443"])

  security_group_id = aws_security_group.host.id
  description       = "Public web (Caddy) port ${each.key}"
  ip_protocol       = "tcp"
  from_port         = tonumber(each.key)
  to_port           = tonumber(each.key)
  cidr_ipv4         = "0.0.0.0/0"
}

resource "aws_vpc_security_group_ingress_rule" "ssh" {
  for_each = toset(var.ssh_allowed_cidrs)

  security_group_id = aws_security_group.host.id
  description       = "SSH from bastion/admin ${each.key}"
  ip_protocol       = "tcp"
  from_port         = 22
  to_port           = 22
  cidr_ipv4         = each.key
}

resource "aws_vpc_security_group_egress_rule" "all" {
  security_group_id = aws_security_group.host.id
  description       = "Outbound (image pulls, OS updates, ACME)"
  ip_protocol       = "-1"
  cidr_ipv4         = "0.0.0.0/0"
}

# Instance role: no static access keys on the server. SSM core lets an operator open a
# Session Manager shell (audited, no port 22) when SSH is unavailable — break-glass, S-02-T10.
data "aws_iam_policy_document" "assume_ec2" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "host" {
  name               = "${var.name}-host"
  assume_role_policy = data.aws_iam_policy_document.assume_ec2.json
}

resource "aws_iam_role_policy_attachment" "ssm_core" {
  role       = aws_iam_role.host.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_instance_profile" "host" {
  name = "${var.name}-host"
  role = aws_iam_role.host.name
}

resource "aws_key_pair" "bootstrap" {
  key_name   = "${var.name}-bootstrap"
  public_key = var.bootstrap_ssh_public_key
}

resource "aws_instance" "host" {
  ami                     = data.aws_ssm_parameter.ami.value
  instance_type           = var.instance_type
  subnet_id               = var.subnet_id
  vpc_security_group_ids  = [aws_security_group.host.id]
  iam_instance_profile    = aws_iam_instance_profile.host.name
  key_name                = aws_key_pair.bootstrap.key_name
  disable_api_termination = var.termination_protection
  monitoring              = false

  metadata_options {
    http_tokens                 = "required" # IMDSv2 only
    http_put_response_hop_limit = 2          # containers on the host may need the role (SSM, later S3)
    http_endpoint               = "enabled"
  }

  root_block_device {
    volume_type           = "gp3"
    volume_size           = var.root_volume_size_gb
    encrypted             = true
    delete_on_termination = true
  }

  tags = { Name = "${var.name}-host" }

  lifecycle {
    # A new Ubuntu AMI must not silently replace a running host; roll hosts deliberately.
    ignore_changes = [ami]
  }
}

# Static public address for DNS (S-02-T07); survives stop/start.
resource "aws_eip" "host" {
  domain   = "vpc"
  instance = aws_instance.host.id
  tags     = { Name = "${var.name}-host" }
}
