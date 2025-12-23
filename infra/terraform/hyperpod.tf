data "aws_caller_identity" "current" {}

resource "aws_s3_bucket" "artifacts" {
  bucket = var.s3_bucket
  tags   = var.tags
}

# HyperPod lifecycle bucket must be sagemaker-... prefixed
resource "aws_s3_bucket" "hp_lifecycle" {
  bucket = "sagemaker-${data.aws_caller_identity.current.account_id}-${var.project}-${var.environment}-hp-lifecycle"
  tags   = var.tags
}

resource "aws_s3_object" "hp_oncreate" {
  bucket = aws_s3_bucket.hp_lifecycle.id
  key    = "Lifecycle-scripts/base-config/on_create.sh"
  source = "${path.module}/lifecycle/on_create.sh"
  etag   = filemd5("${path.module}/lifecycle/on_create.sh")
}

resource "aws_iam_role" "hp_instance_role" {
  name = "${var.project}-${var.environment}-hp-instance-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17",
    Statement = [{
      Effect = "Allow",
      Principal = { Service = "sagemaker.amazonaws.com" },
      Action = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "hp_instance_managed" {
  role       = aws_iam_role.hp_instance_role.name
  policy_arn  = "arn:aws:iam::aws:policy/AmazonSageMakerClusterInstanceRolePolicy"
}

resource "aws_security_group" "hp" {
  name        = "${var.project}-${var.environment}-hp-sg"
  description = "HyperPod worker SG"
  vpc_id      = module.vpc.vpc_id
  tags        = var.tags
}

# Adjust rules for your network posture (internal traffic, EFA, etc.)
resource "aws_vpc_security_group_egress_rule" "hp_all_egress" {
  security_group_id = aws_security_group.hp.id
  ip_protocol       = "-1"
  cidr_ipv4         = "0.0.0.0/0"
}

resource "awscc_sagemaker_cluster" "hp" {
  cluster_name = var.hyperpod_cluster_name

  orchestrator = {
    eks = {
      cluster_arn = module.eks.cluster_arn
    }
  }

  vpc_config = {
    subnets            = module.vpc.private_subnets
    security_group_ids = [aws_security_group.hp.id]
  }

  node_provisioning_mode = "Continuous"
  node_recovery          = "Automatic"

  instance_groups = [
    {
      instance_group_name = "gpu-workers"
      instance_type       = var.hyperpod_instance_type
      instance_count      = var.hyperpod_instance_count
      execution_role      = aws_iam_role.hp_instance_role.arn

      life_cycle_config = {
        source_s3_uri = "s3://${aws_s3_bucket.hp_lifecycle.bucket}/Lifecycle-scripts/base-config/"
        on_create     = "on_create.sh"
      }
    }
  ]

  depends_on = [
    helm_release.hyperpod_dependencies
  ]
}
