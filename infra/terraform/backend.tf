terraform {
  backend "s3" {
    bucket         = "nlp-rmm-tf-state-eu-west-1"
    key            = "infra/terraform.tfstate"
    region         = "eu-west-1"
    dynamodb_table = "nlp-rmm-tf-lock"
    encrypt        = true
  }
}
