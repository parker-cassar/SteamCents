terraform {
  required_version = ">= 1.5"
  required_providers {
    hcloud = {
      source  = "hetznercloud/hcloud"
      version = "~> 1.48"
    }
  }
}

variable "hcloud_token" {
  type      = string
  sensitive = true
}

variable "server_type" {
  type        = string
  default     = "cpx22"
  description = "cax11 is arm and cheaper but nbg1 capacity comes and goes. cpx22 always allocates."
}

variable "location" {
  type    = string
  default = "nbg1"
}

variable "api_domain" {
  type    = string
  default = "api.steamcents.com"
}

variable "acme_email" {
  type        = string
  default     = ""
  description = "where letsencrypt sends expiry warnings. caddy works without one."
}

variable "repo_url" {
  type    = string
  default = "https://github.com/parker-cassar/steam_price.git"
}

provider "hcloud" {
  token = var.hcloud_token
}

resource "hcloud_ssh_key" "me" {
  name       = "steamcents"
  public_key = file("~/.ssh/steamcents.pub")
}

resource "hcloud_firewall" "fw" {
  name = "steamcents-fw"

  dynamic "rule" {
    for_each = ["22", "80", "443"]
    content {
      direction  = "in"
      protocol   = "tcp"
      port       = rule.value
      source_ips = ["0.0.0.0/0", "::/0"]
    }
  }
}

resource "hcloud_server" "app" {
  name         = "steamcents"
  server_type  = var.server_type
  image        = "ubuntu-24.04"
  location     = var.location
  ssh_keys     = [hcloud_ssh_key.me.id]
  firewall_ids = [hcloud_firewall.fw.id]

  public_net {
    ipv4_enabled = true
    ipv6_enabled = true
  }

  user_data = templatefile("${path.module}/cloud-init.yaml", {
    repo_url   = var.repo_url
    api_domain = var.api_domain
    acme_email = var.acme_email
    ssh_key    = file("~/.ssh/steamcents.pub")
  })
}

output "ip" {
  value = hcloud_server.app.ipv4_address
}

output "ssh" {
  value = "ssh -i ~/.ssh/steamcents deploy@${hcloud_server.app.ipv4_address}"
}

output "dns" {
  value = "point ${var.api_domain} at ${hcloud_server.app.ipv4_address} before caddy can get a cert"
}
