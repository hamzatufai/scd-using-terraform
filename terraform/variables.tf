variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Project name"
  type        = string
  default     = "scd-snowflake-airflow"
}

variable "s3_bucket_name" {
  description = "S3 bucket name"
  type        = string
  default     = "s3-scd-snowflake-airflow-2026"
}

variable "instance_type" {
  description = "EC2 instance type"
  type        = string
  default     = "m7i-flex.large"
}

variable "root_volume_size" {
  description = "EC2 root volume size in GB"
  type        = number
  default     = 30
}

variable "storage_aws_iam_user_arn" {
  description = "Snowflake IAM user ARN"
  type        = string
}

variable "storage_aws_external_id" {
  description = "Snowflake external ID"
  type        = string
  sensitive   = true
}