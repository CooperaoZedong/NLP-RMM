resource "kubernetes_namespace" "inference" {
  metadata { name = var.inference_namespace }
}

# Inference operator chart (vendored)
resource "helm_release" "hyperpod_inference_operator" {
  name      = "hyperpod-inference-operator"
  namespace = "kube-system"
  chart     = "${path.module}/../../vendor/sagemaker-hyperpod-cli/helm_chart/HyperPodHelmChart/charts/inference-operator"

  # Pass cluster ARN if your chart expects it (depends on chart values schema)
  # set { name = "hyperpodClusterArn", value = data.terraform_remote_state.infra.outputs.hyperpod_cluster_arn }

  # You typically also need the AWS LB Controller installed if you want LoadBalancer exposure.
}

resource "kubernetes_manifest" "inference_endpoint" {
  manifest = {
    apiVersion = "inference.sagemaker.aws.amazon.com/v1alpha1"
    kind       = "InferenceEndpointConfig"
    metadata = {
      name      = var.endpoint_name
      namespace = var.inference_namespace
    }
    spec = {
      modelName    = var.endpoint_name
      endpointName = var.endpoint_name

      modelSourceConfig = {
        modelSourceType = "s3"
        s3Storage = {
          bucketName = var.model_s3_bucket
          region     = var.region
        }
        modelLocation   = var.model_s3_prefix
        prefetchEnabled = true
      }

      # If you want external access
      loadBalancer = {
        healthCheckPath = "/health"
      }

      worker = {
        image = var.inference_image

        modelInvocationPort = { containerPort = 8000, name = "http" }
        modelVolumeMount    = { name = "model-weights", mountPath = "/opt/ml/model" }

        resources = {
          limits   = { "nvidia.com/gpu" = 1 }
          requests = { "nvidia.com/gpu" = 1, cpu = "8", memory = "64Gi" }
        }

        environmentVariables = [
          { name = "SAGEMAKER_ENV", value = "1" }
        ]
      }
    }
  }

  depends_on = [helm_release.hyperpod_inference_operator]
}
