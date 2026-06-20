variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "region" {
  description = "GCP region for all resources"
  type        = string
  default     = "us-central1"
}

# gemini_api_key has been removed — GOOGLE_API_KEY is now stored in Secret
# Manager and injected into Cloud Run via --set-secrets in cloudbuild.yaml.
# Remove this variable from your terraform.tfvars / CI env if present.

variable "alert_email" {
  description = "Email address for production alerts"
  type        = string
  default     = "dimitri.derose@deepvalueanalysis.io"
}

variable "billing_account_id" {
  description = "GCP billing account ID (format: XXXXXX-XXXXXX-XXXXXX)"
  type        = string
  default     = ""
}

variable "monthly_budget_usd" {
  description = "Monthly budget in USD"
  type        = number
  default     = 100
}
