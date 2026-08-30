terraform {
  required_version = ">= 1.5"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

variable "instance_type" {
  type    = string
  default = "t4g.small"
}

variable "api_domain" {
  type    = string
  default = "api.steamcents.com"
}

variable "acme_email" {
  type        = string
  default     = ""
  description = "letsencrypt expiry warnings. caddy works without one."
}

variable "repo_url" {
  type    = string
  default = "https://github.com/parker-cassar/steam_price.git"
}

variable "ssh_public_key_path" {
  type    = string
  default = "~/.ssh/steamcents.pub"
}

provider "aws" {
  region = "us-east-2"
}

data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"]

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssm/ubuntu-noble-24.04-arm64-server-*"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

resource "aws_key_pair" "me" {
  key_name   = "steamcents"
  public_key = file(var.ssh_public_key_path)
}

resource "aws_security_group" "app" {
  name        = "steamcents"
  description = "ssh, http, https"

  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_instance" "app" {
  ami                    = data.aws_ami.ubuntu.id
  instance_type          = var.instance_type
  key_name               = aws_key_pair.me.key_name
  vpc_security_group_ids = [aws_security_group.app.id]

  root_block_device {
    volume_size = 30
    volume_type = "gp3"
  }

  user_data = templatefile("${path.module}/cloud-init.yaml", {
    repo_url   = var.repo_url
    api_domain = var.api_domain
    acme_email = var.acme_email
    ssh_key    = trimspace(file(var.ssh_public_key_path))
  })

  tags = {
    Name = "steamcents"
  }
}

resource "aws_eip" "app" {
  domain = "vpc"

  instance = aws_instance.app.id

  tags = {
    Name = "steamcents"
  }
}

output "ip" {
  value = aws_eip.app.public_ip
}

output "ssh" {
  value = "ssh -i ~/.ssh/steamcents deploy@${aws_eip.app.public_ip}"
}

output "dns" {
  value = "point ${var.api_domain} A record at ${aws_eip.app.public_ip} before caddy can get a cert"
}
