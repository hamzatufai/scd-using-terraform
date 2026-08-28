output "s3_bucket_name" {
  description = "S3 bucket name"
  value       = aws_s3_bucket.my_bucket.bucket
}

output "s3_bucket_arn" {
  description = "S3 bucket ARN"
  value       = aws_s3_bucket.my_bucket.arn
}

output "ec2_instance_id" {
  description = "EC2 instance ID"
  value       = aws_instance.ec2_instance.id
}

output "ec2_public_ip" {
  description = "EC2 public IP"
  value       = aws_instance.ec2_instance.public_ip
}

output "ec2_public_dns" {
  description = "EC2 public DNS"
  value       = aws_instance.ec2_instance.public_dns
}

output "ec2_role_name" {
  description = "EC2 IAM role"
  value       = aws_iam_role.ec2_role.name
}

output "snowflake_role_arn" {
  description = "Snowflake IAM role ARN"
  value       = aws_iam_role.snowflake_role.arn
}

output "ssh_private_key_file" {
  description = "SSH private key file"
  value       = local_file.private_key_pem.filename
}