output "s3_bucket"   { value = aws_s3_bucket.artifacts.bucket }
output "kms_key_arn" { value = aws_kms_key.s3_kms.arn }
output "sagemaker_role_arn" { value = aws_iam_role.sagemaker_exec.arn }
output "region" { value = var.region }

output "eks_cluster_name" { value = module.eks.cluster_name }
output "eks_cluster_arn"  { value = module.eks.cluster_arn }

output "vpc_id"              { value = module.vpc.vpc_id }
output "private_subnet_ids"  { value = module.vpc.private_subnets }
output "public_subnet_ids"   { value = module.vpc.public_subnets }

output "hyperpod_cluster_name" { value = awscc_sagemaker_cluster.hp.cluster_name }
output "hyperpod_cluster_arn"  { value = awscc_sagemaker_cluster.hp.cluster_arn }

output "artifacts_bucket"      { value = aws_s3_bucket.artifacts.bucket }
output "hp_lifecycle_bucket"   { value = aws_s3_bucket.hp_lifecycle.bucket }

output "hp_instance_role_arn"  { value = aws_iam_role.hp_instance_role.arn }
