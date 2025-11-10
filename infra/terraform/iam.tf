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
