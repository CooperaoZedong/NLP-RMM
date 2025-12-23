# IAM role for SageMaker execution
data "aws_iam_policy_document" "sagemaker_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type = "Service"
      identifiers = ["sagemaker.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "sagemaker_exec" {
  name               = "${var.project}-sagemaker-exec"
  assume_role_policy = data.aws_iam_policy_document.sagemaker_assume.json
  tags               = var.tags
}

# sagemaker access policy
data "aws_iam_policy_document" "sagemaker_access" {
  statement {
    actions   = ["s3:ListBucket"]
    resources = [aws_s3_bucket.artifacts.arn]
  }
  statement {
    actions   = ["s3:GetObject","s3:PutObject","s3:DeleteObject"]
    resources = ["${aws_s3_bucket.artifacts.arn}/*"]
  }
  statement {
    actions   = ["logs:CreateLogGroup","logs:CreateLogStream","logs:PutLogEvents"]
    resources = ["*"]
  }
  statement {
    actions   = ["kms:Encrypt","kms:Decrypt","kms:GenerateDataKey*","kms:DescribeKey"]
    resources = [aws_kms_key.s3_kms.arn]
  }
}

resource "aws_iam_policy" "sagemaker_access" {
  name   = "${var.project}-sagemaker-access"
  policy = data.aws_iam_policy_document.sagemaker_access.json
}

resource "aws_iam_role_policy_attachment" "attach" {
  role       = aws_iam_role.sagemaker_exec.name
  policy_arn = aws_iam_policy.sagemaker_access.arn
}

# IAM role for Grafana workspace
data "aws_iam_policy_document" "grafana_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["grafana.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "grafana_workspace" {
  name               = "${var.project}-grafana-workspace-role"
  assume_role_policy = data.aws_iam_policy_document.grafana_assume_role.json
}

# Minimal CloudWatch read access for metrics
resource "aws_iam_policy" "grafana_cloudwatch_read" {
  name        = "${var.project}-grafana-cloudwatch-read"
  description = "Read-only access to CloudWatch metrics for ${var.project}"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "cloudwatch:GetMetricData",
          "cloudwatch:GetMetricStatistics",
          "cloudwatch:ListMetrics"
        ]
        Resource = "*"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "grafana_cloudwatch_read_attach" {
  role       = aws_iam_role.grafana_workspace.name
  policy_arn = aws_iam_policy.grafana_cloudwatch_read.arn
}
