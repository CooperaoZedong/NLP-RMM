resource "aws_kms_key" "s3_kms" {
  description             = "${var.project} s3 kms"
  deletion_window_in_days = 7
  enable_key_rotation     = true
  tags = var.tags
}
