output "s3_bucket"   { value = aws_s3_bucket.artifacts.bucket }
output "kms_key_arn" { value = aws_kms_key.s3_kms.arn }
output "sagemaker_role_arn" { value = aws_iam_role.sagemaker_exec.arn }
