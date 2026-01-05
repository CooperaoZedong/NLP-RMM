# --- Service Accounts ---
resource "kubernetes_namespace" "inference" {
  metadata { name = var.inference_namespace }
}

resource "kubernetes_service_account" "inference_sa" {
  metadata {
    name      = "hp-inference-sa"
    namespace = kubernetes_namespace.inference.metadata[0].name
  }
}

resource "kubernetes_service_account" "training_sa" {
  metadata {
    name      = "hp-training-sa"
    namespace = "aws-hyperpod"
  }
}

# --- IAM trust for Pod Identity ---
data "aws_iam_policy_document" "pod_identity_trust" {
  statement {
    actions = ["sts:AssumeRole", "sts:TagSession"]
    principals {
      type        = "Service"
      identifiers = ["pods.eks.amazonaws.com"]
    }
  }
}

# Inference role: read model artifacts + decrypt KMS
resource "aws_iam_role" "inference_pod_role" {
  name               = "hp-inference-pod-role"
  assume_role_policy = data.aws_iam_policy_document.pod_identity_trust.json
}

data "aws_iam_policy_document" "inference_policy" {
  statement {
    actions   = ["s3:ListBucket"]
    resources = [data.terraform_remote_state.infra.outputs.s3_bucket]
    condition {
      test     = "StringLike"
      variable = "s3:prefix"
      values   = ["${var.model_s3_prefix}*"]
    }
  }

  statement {
    actions = ["s3:GetObject"]
    resources = [
      "${data.terraform_remote_state.infra.outputs.s3_bucket}/${var.model_s3_prefix}*"
    ]
  }

  statement {
    actions   = ["kms:Decrypt", "kms:DescribeKey"]
    resources = [data.terraform_remote_state.infra.outputs.kms_key_arn]
  }

  statement {
    actions   = ["logs:CreateLogGroup","logs:CreateLogStream","logs:PutLogEvents"]
    resources = ["*"]
  }
}

resource "aws_iam_policy" "inference_policy" {
  name   = "hp-inference-policy"
  policy = data.aws_iam_policy_document.inference_policy.json
}

resource "aws_iam_role_policy_attachment" "inference_attach" {
  role       = aws_iam_role.inference_pod_role.name
  policy_arn = aws_iam_policy.inference_policy.arn
}

# Training role: read code/data + write outputs + KMS encrypt/decrypt
resource "aws_iam_role" "training_pod_role" {
  name               = "hp-training-pod-role"
  assume_role_policy = data.aws_iam_policy_document.pod_identity_trust.json
}

data "aws_iam_policy_document" "training_policy" {
  statement {
    actions   = ["s3:ListBucket"]
    resources = [data.terraform_remote_state.infra.outputs.s3_bucket]
  }

  statement {
    actions = ["s3:GetObject"]
    resources = [
      "${data.terraform_remote_state.infra.outputs.s3_bucket}/${data.terraform_remote_state.infra.outputs.s3_code_prefix}/*",
      "${data.terraform_remote_state.infra.outputs.s3_bucket}/${data.terraform_remote_state.infra.outputs.s3_data_prefix}/*",
    ]
  }

  # outputs/checkpoints
  statement {
    actions = ["s3:PutObject", "s3:AbortMultipartUpload"]
    resources = [
      "${data.terraform_remote_state.infra.outputs.s3_bucket}/runs/*"
    ]
  }

  statement {
    actions   = ["kms:Encrypt","kms:Decrypt","kms:GenerateDataKey*","kms:DescribeKey"]
    resources = [data.terraform_remote_state.infra.outputs.kms_key_arn]
  }

  statement {
    actions   = ["logs:CreateLogGroup","logs:CreateLogStream","logs:PutLogEvents"]
    resources = ["*"]
  }
}

resource "aws_iam_policy" "training_policy" {
  name   = "hp-training-policy"
  policy = data.aws_iam_policy_document.training_policy.json
}

resource "aws_iam_role_policy_attachment" "training_attach" {
  role       = aws_iam_role.training_pod_role.name
  policy_arn = aws_iam_policy.training_policy.arn
}

# --- Pod Identity associations ---
resource "aws_eks_pod_identity_association" "inference_assoc" {
  cluster_name        = data.terraform_remote_state.infra.outputs.eks_cluster_name
  namespace           = kubernetes_namespace.inference.metadata[0].name
  service_account_name = kubernetes_service_account.inference_sa.metadata[0].name
  role_arn            = aws_iam_role.inference_pod_role.arn
}

resource "aws_eks_pod_identity_association" "training_assoc" {
  cluster_name        = data.terraform_remote_state.infra.outputs.eks_cluster_name
  namespace           = "aws-hyperpod"
  service_account_name = kubernetes_service_account.training_sa.metadata[0].name
  role_arn            = aws_iam_role.training_pod_role.arn
}
