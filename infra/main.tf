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

data "aws_caller_identity" "current" {}

data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"]

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd-gp3/ubuntu-noble-24.04-arm64-server-*"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

resource "aws_s3_bucket" "backups" {
  bucket = "steamcents-backups-${data.aws_caller_identity.current.account_id}"
}

resource "aws_s3_bucket_public_access_block" "backups" {
  bucket = aws_s3_bucket.backups.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
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

# allocate first so dns can start propagating before the instance exists
resource "aws_eip" "app" {
  domain = "vpc"

  tags = {
    Name = "steamcents"
  }
}

resource "aws_iam_role" "ec2" {
  name = "steamcents-ec2"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "ec2.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy" "backup_s3" {
  name = "steamcents-backup-s3"
  role = aws_iam_role.ec2.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["s3:PutObject", "s3:GetObject", "s3:ListBucket"]
      Resource = [
        aws_s3_bucket.backups.arn,
        "${aws_s3_bucket.backups.arn}/*",
      ]
    }]
  })
}

resource "aws_iam_instance_profile" "ec2" {
  name = "steamcents-ec2"
  role = aws_iam_role.ec2.name
}

resource "aws_instance" "app" {
  ami                    = data.aws_ami.ubuntu.id
  instance_type          = var.instance_type
  key_name               = aws_key_pair.me.key_name
  vpc_security_group_ids = [aws_security_group.app.id]
  iam_instance_profile   = aws_iam_instance_profile.ec2.name

  root_block_device {
    volume_size = 30
    volume_type = "gp3"
  }

  user_data = templatefile("${path.module}/cloud-init.yaml", {
    repo_url       = var.repo_url
    api_domain     = var.api_domain
    acme_email     = var.acme_email
    ssh_key        = trimspace(file(var.ssh_public_key_path))
    backup_bucket  = aws_s3_bucket.backups.bucket
  })

  tags = {
    Name = "steamcents"
  }
}

resource "aws_eip_association" "app" {
  allocation_id = aws_eip.app.id
  instance_id   = aws_instance.app.id
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

output "backup_bucket" {
  value = aws_s3_bucket.backups.bucket
}
