############################################
# S3 BUCKET
############################################

resource "aws_s3_bucket" "my_bucket" {
  bucket        = var.s3_bucket_name
  force_destroy = true

  tags = {
    Name        = var.s3_bucket_name
    Environment = "Dev"
    Project     = var.project_name
    ManagedBy   = "Terraform"
  }
}

############################################
# S3 VERSIONING
############################################

resource "aws_s3_bucket_versioning" "my_bucket" {
  bucket = aws_s3_bucket.my_bucket.id

  versioning_configuration {
    status = "Enabled"
  }
}

############################################
# S3 SERVER-SIDE ENCRYPTION
############################################

resource "aws_s3_bucket_server_side_encryption_configuration" "my_bucket" {
  bucket = aws_s3_bucket.my_bucket.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

############################################
# BLOCK PUBLIC ACCESS
############################################

resource "aws_s3_bucket_public_access_block" "my_bucket" {
  bucket = aws_s3_bucket.my_bucket.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

############################################
# EC2 IAM ROLE
############################################

resource "aws_iam_role" "ec2_role" {
  name = "${var.project_name}-ec2-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"

    Statement = [
      {
        Effect = "Allow"

        Principal = {
          Service = "ec2.amazonaws.com"
        }

        Action = "sts:AssumeRole"
      }
    ]
  })

  tags = {
    Name      = "${var.project_name}-ec2-role"
    Project   = var.project_name
    ManagedBy = "Terraform"
  }
}

############################################
# EC2 → S3 IAM POLICY
#
# Airflow can read/write the project bucket
############################################

resource "aws_iam_policy" "ec2_s3_policy" {
  name        = "${var.project_name}-s3-policy"
  description = "Allow Airflow EC2 to access project S3 bucket"

  policy = jsonencode({
    Version = "2012-10-17"

    Statement = [
      {
        Effect = "Allow"

        Action = [
          "s3:ListBucket"
        ]

        Resource = aws_s3_bucket.my_bucket.arn
      },

      {
        Effect = "Allow"

        Action = [
          "s3:GetObject",
          "s3:GetObjectVersion",
          "s3:PutObject",
          "s3:DeleteObject"
        ]

        Resource = "${aws_s3_bucket.my_bucket.arn}/*"
      }
    ]
  })

  tags = {
    Name      = "${var.project_name}-s3-policy"
    Project   = var.project_name
    ManagedBy = "Terraform"
  }
}

############################################
# ATTACH EC2 S3 POLICY
############################################

resource "aws_iam_role_policy_attachment" "ec2_s3_policy" {
  role       = aws_iam_role.ec2_role.name
  policy_arn = aws_iam_policy.ec2_s3_policy.arn
}

############################################
# SNOWFLAKE IAM ROLE
############################################

resource "aws_iam_role" "snowflake_role" {
  name = "${var.project_name}-snowflake-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"

    Statement = [
      {
        Effect = "Allow"

        Principal = {
          AWS = var.storage_aws_iam_user_arn
        }

        Action = "sts:AssumeRole"

        Condition = {
          StringEquals = {
            "sts:ExternalId" = var.storage_aws_external_id
          }
        }
      }
    ]
  })

  tags = {
    Name      = "${var.project_name}-snowflake-role"
    Project   = var.project_name
    ManagedBy = "Terraform"
  }
}

############################################
# SNOWFLAKE → S3 IAM POLICY
############################################

resource "aws_iam_policy" "snowflake_s3_policy" {
  name        = "${var.project_name}-snowflake-s3-policy"
  description = "Allow Snowflake to read project S3 bucket"

  policy = jsonencode({
    Version = "2012-10-17"

    Statement = [
      {
        Effect = "Allow"

        Action = [
          "s3:ListBucket"
        ]

        Resource = aws_s3_bucket.my_bucket.arn
      },

      {
        Effect = "Allow"

        Action = [
          "s3:GetObject",
          "s3:GetObjectVersion"
        ]

        Resource = "${aws_s3_bucket.my_bucket.arn}/*"
      }
    ]
  })

  tags = {
    Name      = "${var.project_name}-snowflake-s3-policy"
    Project   = var.project_name
    ManagedBy = "Terraform"
  }
}

############################################
# ATTACH SNOWFLAKE POLICY
############################################

resource "aws_iam_role_policy_attachment" "snowflake_s3_policy" {
  role       = aws_iam_role.snowflake_role.name
  policy_arn = aws_iam_policy.snowflake_s3_policy.arn
}

############################################
# EC2 INSTANCE PROFILE
############################################

resource "aws_iam_instance_profile" "ec2_profile" {
  name = "${var.project_name}-instance-profile"
  role = aws_iam_role.ec2_role.name
}

############################################
# AMAZON LINUX 2023 AMI
############################################

data "aws_ami" "amazon_linux_2023" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name = "name"

    values = [
      "al2023-ami-2023*-x86_64"
    ]
  }

  filter {
    name = "state"

    values = [
      "available"
    ]
  }
}

############################################
# DEFAULT VPC
############################################

data "aws_vpc" "default" {
  default = true
}

############################################
# EC2 SUBNET
############################################

data "aws_subnet" "ec2_subnet" {
  filter {
    name = "vpc-id"

    values = [
      data.aws_vpc.default.id
    ]
  }

  filter {
    name = "availability-zone"

    values = [
      "us-east-1a"
    ]
  }
}

############################################
# SECURITY GROUP
############################################

resource "aws_security_group" "ec2_sg" {
  name        = "${var.project_name}-sg"
  description = "Security group for Airflow EC2"
  vpc_id      = data.aws_vpc.default.id

  ##########################################
  # SSH
  ##########################################

  ingress {
    description = "SSH access"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"

    cidr_blocks = [
      "0.0.0.0/0"
    ]
  }

  ##########################################
  # AIRFLOW UI
  ##########################################

  ingress {
    description = "Airflow Web UI"
    from_port   = 8080
    to_port     = 8080
    protocol    = "tcp"

    cidr_blocks = [
      "0.0.0.0/0"
    ]
  }

  ##########################################
  # OUTBOUND
  ##########################################

  egress {
    description = "Allow all outbound traffic"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"

    cidr_blocks = [
      "0.0.0.0/0"
    ]
  }

  tags = {
    Name        = "${var.project_name}-sg"
    Environment = "Dev"
    Project     = var.project_name
    ManagedBy   = "Terraform"
  }
}

############################################
# GENERATE SSH KEY
############################################

resource "tls_private_key" "ssh_key" {
  algorithm = "RSA"
  rsa_bits  = 4096
}

############################################
# REGISTER SSH KEY IN AWS
############################################

resource "aws_key_pair" "keypair" {
  key_name   = "${var.project_name}-key"
  public_key = tls_private_key.ssh_key.public_key_openssh

  tags = {
    Name      = "${var.project_name}-key"
    Project   = var.project_name
    ManagedBy = "Terraform"
  }
}

############################################
# SAVE PRIVATE KEY LOCALLY
############################################

resource "local_file" "private_key_pem" {
  content = tls_private_key.ssh_key.private_key_pem

  filename = "${path.module}/${var.project_name}.pem"

  file_permission = "0600"
}

############################################
# EC2 INSTANCE
############################################

resource "aws_instance" "ec2_instance" {

  ami = data.aws_ami.amazon_linux_2023.id

  instance_type = var.instance_type

  subnet_id = data.aws_subnet.ec2_subnet.id

  vpc_security_group_ids = [
    aws_security_group.ec2_sg.id
  ]

  key_name = aws_key_pair.keypair.key_name

  iam_instance_profile = aws_iam_instance_profile.ec2_profile.name

  root_block_device {
    volume_type           = "gp3"
    volume_size           = var.root_volume_size
    encrypted             = true
    delete_on_termination = true
  }

  depends_on = [
    aws_s3_bucket.my_bucket,
    aws_iam_role_policy_attachment.ec2_s3_policy
  ]

  tags = {
    Name        = "${var.project_name}-ec2"
    Environment = "Dev"
    Project     = var.project_name
    ManagedBy   = "Terraform"
  }
}