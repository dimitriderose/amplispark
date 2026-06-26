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
    "secretmanager.googleapis.com",
    "clouderrorreporting.googleapis.com",
    "monitoring.googleapis.com",
    "billingbudgets.googleapis.com",
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

resource "google_firestore_index" "brands_by_owner_created_at" {
  project     = var.project_id
  database    = google_firestore_database.default.name
  collection  = "brands"
  query_scope = "COLLECTION"

  fields {
    field_path = "owner_uid"
    order      = "ASCENDING"
  }
  fields {
    field_path = "created_at"
    order      = "DESCENDING"
  }
  fields {
    field_path = "__name__"
    order      = "DESCENDING"
  }

  depends_on = [google_firestore_database.default]
}

resource "google_firestore_index" "notifications_read_created_at" {
  project     = var.project_id
  database    = google_firestore_database.default.name
  collection  = "notifications"
  query_scope = "COLLECTION_GROUP"

  fields {
    field_path = "read"
    order      = "ASCENDING"
  }
  fields {
    field_path = "created_at"
    order      = "DESCENDING"
  }
  fields {
    field_path = "__name__"
    order      = "DESCENDING"
  }

  depends_on = [google_firestore_database.default]
}

resource "google_firestore_field" "notifications_ttl" {
  project    = var.project_id
  database   = google_firestore_database.default.name
  collection = "notifications"
  field      = "created_at"

  ttl_config {}

  depends_on = [google_firestore_database.default]
}

# ── Cloud Storage bucket (generated images + video) ─────────────────────────

resource "google_storage_bucket" "assets" {
  name          = "${var.project_id}-amplifi-assets"
  location      = var.region
  force_destroy = false

  uniform_bucket_level_access = true

  depends_on = [google_project_service.apis]
}

# ── Artifact Registry (Docker images) ────────────────────────────────────────

resource "google_artifact_registry_repository" "docker" {
  repository_id = "amplifi"
  location      = var.region
  format        = "DOCKER"
  description   = "Amplispark container images"

  cleanup_policies {
    id     = "delete-untagged"
    action = "DELETE"
    condition {
      tag_state  = "UNTAGGED"
      older_than = "604800s"  # 7 days
    }
  }

  depends_on = [google_project_service.apis]
}

# ── Secret Manager secrets ───────────────────────────────────────────────────

data "google_project" "project" {}

resource "google_secret_manager_secret" "google_api_key" {
  secret_id  = "GOOGLE_API_KEY"
  replication { auto {} }
  depends_on = [google_project_service.apis]
}

resource "google_secret_manager_secret" "token_encrypt_key" {
  secret_id  = "TOKEN_ENCRYPT_KEY"
  replication { auto {} }
  depends_on = [google_project_service.apis]
}

resource "google_secret_manager_secret" "resend_api_key" {
  secret_id  = "RESEND_API_KEY"
  replication { auto {} }
  depends_on = [google_project_service.apis]
}

resource "google_secret_manager_secret" "notion_client_secret" {
  secret_id  = "NOTION_CLIENT_SECRET"
  replication { auto {} }
  depends_on = [google_project_service.apis]
}

# Compute default SA → used by Cloud Run at request time to resolve secrets
resource "google_project_iam_member" "secret_accessor" {
  project = var.project_id
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${data.google_project.project.number}-compute@developer.gserviceaccount.com"
}

# Cloud Build SA → needed to execute `gcloud run deploy --set-secrets` in cloudbuild.yaml
resource "google_project_iam_member" "cloudbuild_secret_accessor" {
  project = var.project_id
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${data.google_project.project.number}@cloudbuild.gserviceaccount.com"
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
      min_instance_count = 1
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

      # GOOGLE_API_KEY is injected via Secret Manager (--set-secrets in cloudbuild.yaml).
      # Do NOT set it here as a plaintext env var.
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
    # Note: nested heredocs inside <<-EOT are unreliable (<<-EOT only strips
    # leading tabs, not spaces; the inner terminator must be at column 0).
    # Instead, pass the CORS JSON via a shell variable to avoid nesting.
    command = <<-EOT
      gcloud run services update amplifi \
        --region ${var.region} \
        --update-env-vars "CORS_ORIGINS=${google_cloud_run_v2_service.amplifi.uri}"
      CORS_JSON='[{"origin":["${google_cloud_run_v2_service.amplifi.uri}"],"method":["GET"],"responseHeader":["Content-Type"],"maxAgeSeconds":3600}]'
      echo "$CORS_JSON" | gcloud storage buckets update gs://${google_storage_bucket.assets.name} \
        --cors-file=/dev/stdin
    EOT
  }

  depends_on = [google_cloud_run_v2_service.amplifi]
}

# ── Monitoring alerts ────────────────────────────────────────────────────────

resource "google_monitoring_notification_channel" "email" {
  display_name = "Amplispark Alerts"
  type         = "email"
  labels = {
    email_address = var.alert_email
  }
  depends_on = [google_project_service.apis]
}

resource "google_monitoring_uptime_check_config" "health" {
  display_name = "Amplispark Health Check"
  timeout      = "10s"
  period       = "60s"

  http_check {
    path         = "/health"
    port         = 443
    use_ssl      = true
    validate_ssl = true
  }

  monitored_resource {
    type = "uptime_url"
    labels = {
      project_id = var.project_id
      host       = trimprefix(google_cloud_run_v2_service.amplifi.uri, "https://")
    }
  }

  depends_on = [google_cloud_run_v2_service.amplifi]
}

resource "google_monitoring_alert_policy" "error_rate" {
  display_name = "Amplispark 5xx Error Rate"
  combiner     = "OR"

  conditions {
    display_name = "5xx error ratio > 1% over 5 min"
    # MQL computes the true ratio: 5xx_rate / total_rate.
    # A condition_threshold with ALIGN_RATE on request_count yields raw
    # requests/second, NOT a percentage — threshold_value = 0.01 there would
    # mean "0.01 req/s of 5xx", which fires at essentially any error.
    condition_monitoring_query_language {
      query    = <<-MQL
        fetch cloud_run_revision
        | metric 'run.googleapis.com/request_count'
        | filter resource.service_name == 'amplifi'
        | align rate(5m)
        | group_by [], [
            err: sum(if(metric.response_code_class == '5xx', val(), 0)),
            total: sum(val())
          ]
        | value [ratio: err / if(total > 0, total, 1)]
        | condition val() > 0.01
      MQL
      duration = "300s"
    }
  }

  notification_channels = [google_monitoring_notification_channel.email.name]
  depends_on            = [google_project_service.apis]
}

resource "google_monitoring_alert_policy" "latency" {
  display_name = "Amplispark p99 Latency"
  combiner     = "OR"

  conditions {
    display_name = "p99 latency > 5s"
    condition_threshold {
      filter          = "resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"amplifi\" AND metric.type=\"run.googleapis.com/request_latencies\""
      duration        = "300s"
      comparison      = "COMPARISON_GT"
      threshold_value = 5000
      aggregations {
        alignment_period     = "300s"
        per_series_aligner   = "ALIGN_DELTA"
        cross_series_reducer = "REDUCE_PERCENTILE_99"
      }
    }
  }

  notification_channels = [google_monitoring_notification_channel.email.name]
  depends_on            = [google_project_service.apis]
}

# ── Budget alerts ─────────────────────────────────────────────────────────────

resource "google_billing_budget" "amplispark" {
  count           = var.billing_account_id != "" ? 1 : 0
  billing_account = var.billing_account_id
  display_name    = "Amplispark Monthly Budget"

  budget_filter {
    projects = ["projects/${data.google_project.project.number}"]
  }

  amount {
    specified_amount {
      currency_code = "USD"
      units         = tostring(floor(var.monthly_budget_usd))
    }
  }

  threshold_rules { threshold_percent = 0.5 }
  threshold_rules { threshold_percent = 0.9 }
  threshold_rules { threshold_percent = 1.0 }

  depends_on = [google_project_service.apis]
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
