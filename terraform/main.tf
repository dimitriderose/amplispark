# ──────────────────────────────────────────────────────────────────────────────
# Amplispark — Terraform IaC
# One-command deployment: enables APIs, provisions Firestore + Cloud Storage,
# builds + deploys the Docker image to Cloud Run with SSE timeout.
# ──────────────────────────────────────────────────────────────────────────────

terraform {
  required_version = ">= 1.5"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
    null = {
      source  = "hashicorp/null"
      version = "~> 3.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# ── Enable required GCP APIs ─────────────────────────────────────────────────

resource "google_project_service" "apis" {
  for_each = toset([
    "run.googleapis.com",
    "cloudbuild.googleapis.com",
    "firestore.googleapis.com",
    "storage.googleapis.com",
    "aiplatform.googleapis.com",
    "artifactregistry.googleapis.com",
  ])
  service            = each.value
  disable_on_destroy = false
}

# ── Cloud Firestore ──────────────────────────────────────────────────────────

resource "google_firestore_database" "default" {
  name        = "(default)"
  location_id = var.region
  type        = "FIRESTORE_NATIVE"

  depends_on = [google_project_service.apis]
}

# ── Cloud Storage bucket (generated images + video) ─────────────────────────

resource "google_storage_bucket" "assets" {
  name          = "${var.project_id}-amplifi-assets"
  location      = var.region
  force_destroy = false

  uniform_bucket_level_access = true

  cors {
    origin          = ["*"]  # Tighten to Cloud Run URL after deploy
    method          = ["GET"]
    response_header = ["Content-Type"]
    max_age_seconds = 3600
  }

  depends_on = [google_project_service.apis]
}

# ── Artifact Registry (Docker images) ────────────────────────────────────────

resource "google_artifact_registry_repository" "docker" {
  repository_id = "amplifi"
  location      = var.region
  format        = "DOCKER"
  description   = "Amplispark container images"

  depends_on = [google_project_service.apis]
}

# ── Cloud Run service ────────────────────────────────────────────────────────

locals {
  image_url = "${var.region}-docker.pkg.dev/${var.project_id}/amplifi/amplifi:latest"
}

resource "google_cloud_run_v2_service" "amplifi" {
  name     = "amplifi"
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL"

  template {
    scaling {
      min_instance_count = 0
      max_instance_count = 10
    }

    timeout = "300s"  # SSE streams can run 2-3 minutes

    containers {
      image = local.image_url

      ports {
        container_port = 8080
      }

      resources {
        limits = {
          cpu    = "2"
          memory = "2Gi"
        }
      }

      env {
        name  = "GOOGLE_API_KEY"
        value = var.gemini_api_key
      }
      env {
        name  = "GCP_PROJECT_ID"
        value = var.project_id
      }
      env {
        name  = "GCS_BUCKET_NAME"
        value = google_storage_bucket.assets.name
      }
      env {
        name  = "CORS_ORIGINS"
        value = ""  # Auto-updated by null_resource.set_cors after deploy
      }
    }
  }

  depends_on = [
    google_project_service.apis,
    google_firestore_database.default,
    google_storage_bucket.assets,
    google_artifact_registry_repository.docker,
  ]
}

# ── Allow unauthenticated access ─────────────────────────────────────────────

resource "google_cloud_run_v2_service_iam_member" "public" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.amplifi.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# ── Auto-set CORS_ORIGINS after deploy ────────────────────────────────────────

resource "null_resource" "set_cors" {
  triggers = {
    service_uri = google_cloud_run_v2_service.amplifi.uri
  }

  provisioner "local-exec" {
    command = <<-EOT
      gcloud run services update amplifi \
        --region ${var.region} \
        --update-env-vars "CORS_ORIGINS=${google_cloud_run_v2_service.amplifi.uri}"
    EOT
  }

  depends_on = [google_cloud_run_v2_service.amplifi]
}

# ── Outputs ──────────────────────────────────────────────────────────────────

output "service_url" {
  description = "Cloud Run URL (CORS_ORIGINS is auto-configured)"
  value       = google_cloud_run_v2_service.amplifi.uri
}

output "image_url" {
  description = "Docker image URL to push to"
  value       = local.image_url
}

output "bucket_name" {
  description = "Cloud Storage bucket for generated assets"
  value       = google_storage_bucket.assets.name
}

output "firestore_database" {
  description = "Firestore database name"
  value       = google_firestore_database.default.name
}
