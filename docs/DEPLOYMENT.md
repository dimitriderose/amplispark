# Amplispark — Deployment Guide

## Prerequisites

| Tool | Version | Purpose |
|------|---------|---------|
| Python | 3.12+ | Backend runtime |
| Node.js | 20+ | Frontend build (TypeScript + Vite 7) |
| npm | 10+ | Frontend package manager |
| Google Cloud SDK (`gcloud`) | Latest | GCP services + deployment |
| Docker | 24+ | Container builds (production) |
| Terraform | 1.5+ | Infrastructure as code (optional, see Part 6) |
| ffmpeg | 6+ | Video processing (installed in Docker, needed locally for video features) |
| Git | 2.x | Source control |

### GCP Services Required

| Service | Purpose | Free Tier? |
|---------|---------|------------|
| **Gemini API** | Brand analysis, content creation (interleaved text+image), review, voice coach | Yes — generous free tier |
| **Cloud Firestore** | Brand profiles, content plans, posts | Yes — 1 GiB free |
| **Cloud Storage** | Generated images, uploaded assets, video clips | Yes — 5 GB free |
| **Cloud Run** | Backend hosting (production) | Yes — 2M requests/month |
| **Cloud Build** | CI/CD pipeline (production) | Yes — 120 build-min/day |
| **Firebase Auth** | Google Sign-In (user authentication) | Yes — unlimited |

---

## Part 1: Local Development

### 1.1 Clone the Repo

```bash
git clone https://github.com/dimitriderose/amplifi-hackaton.git
cd amplifi-hackaton
```

### 1.2 Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv .venv
source .venv/bin/activate    # macOS/Linux
# .venv\Scripts\activate     # Windows

# Install dependencies
pip install -r requirements.txt
```

**Dependencies installed:**
- `fastapi==0.115.0` + `uvicorn[standard]==0.30.0` — ASGI web framework
- `google-adk>=1.25.0` — Google Agent Development Kit (ADK sequential pipeline)
- `google-genai>=1.64.0` — Gemini API (interleaved text+image generation)
- `google-cloud-firestore==2.19.0` — Firestore client
- `google-cloud-storage==2.18.0` — Cloud Storage client (images, video)
- `httpx==0.27.0` — Async HTTP (web scraping, external API calls)
- `beautifulsoup4==4.12.3` — HTML parsing (brand URL scraping)
- `pydantic==2.9.0` — Data models
- `python-dotenv==1.0.0` — Environment variable loading
- `python-multipart==0.0.9` — File upload handling
- `sse-starlette==1.8.2` — Server-Sent Events (streaming generation)
- `cryptography==42.0.0` — Fernet encryption for Notion OAuth token storage
- `firebase-admin==6.5.0` — Firebase Admin SDK for ID token verification

### 1.3 Environment Variables

**Backend** — copy `backend/.env.example` to `backend/.env`:

```bash
cd backend
cp .env.example .env
```

Edit `backend/.env`:

```env
# === REQUIRED ===
GOOGLE_API_KEY=your-gemini-api-key
GCP_PROJECT_ID=your-gcp-project-id

# === STORAGE ===
GCS_BUCKET_NAME=your-project-id-amplifi-assets

# === CORS ===
CORS_ORIGINS=http://localhost:5173

# === OPTIONAL: Gemini model override ===
GEMINI_MODEL=gemini-3-flash-preview

# === OPTIONAL: Token encryption (Notion OAuth) ===
# Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
TOKEN_ENCRYPT_KEY=your-fernet-key
```

**Frontend** — create `frontend/.env.local` with your Firebase config:

```env
VITE_FIREBASE_API_KEY=your-firebase-api-key
VITE_FIREBASE_AUTH_DOMAIN=your-project.firebaseapp.com
VITE_FIREBASE_PROJECT_ID=your-firebase-project-id
VITE_FIREBASE_STORAGE_BUCKET=your-project.firebasestorage.app
VITE_FIREBASE_MESSAGING_SENDER_ID=your-sender-id
VITE_FIREBASE_APP_ID=your-app-id
```

**Getting credentials:**

1. **Gemini API Key:** Go to [Google AI Studio](https://aistudio.google.com/apikey) → Create API Key
2. **GCP Project:** `gcloud projects create amplifi-hackathon` (or use existing)
3. **Firebase Project:** Go to [Firebase Console](https://console.firebase.google.com) → Add Project (or link existing GCP project) → Enable Google Sign-In under Authentication → Providers → Copy web app config
4. **Authentication (local dev):**
   ```bash
   gcloud auth application-default login
   ```
   This uses ADC (Application Default Credentials) — no service account file needed locally.
5. **Cloud Storage Bucket:**
   ```bash
   gcloud storage buckets create gs://YOUR_PROJECT_ID-amplifi-assets \
     --location=us-central1 \
     --uniform-bucket-level-access
   ```
6. **Firestore:**
   ```bash
   gcloud firestore databases create --location=nam5 --type=firestore-native
   ```
7. **Firestore IAM (Cloud Run):**
   ```bash
   gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
     --member="serviceAccount:YOUR_PROJECT_NUMBER-compute@developer.gserviceaccount.com" \
     --role="roles/datastore.user"
   ```

### 1.4 Start the Backend

```bash
cd backend
uvicorn server:app --host 0.0.0.0 --port 8080 --reload
```

**Note:** Amplispark's backend is `server.py` (not `main.py`) and runs on port **8080** (not 8000).

Verify: `curl http://localhost:8080/health`

### 1.5 Frontend Setup

Open a **new terminal**:

```bash
cd frontend
npm install
npm run dev
```

This starts Vite on `http://localhost:5173` with HMR. The Vite config proxies:
- `/api/*` → `http://localhost:8080` (REST + SSE endpoints)
- `/health` → `http://localhost:8080`

**Note:** The frontend is TypeScript (`.tsx`) with React 19, Vite 7, and ESLint. The build step is `tsc -b && vite build`.

### 1.6 Test Locally

1. Open `http://localhost:5173` in your browser
2. Click "Build My Brand Profile" → sign in with Google
3. You'll land on the **Brands page** — click "+ New Brand"
4. Describe your business (or paste a URL)
5. Watch brand analysis run → content calendar generates via SSE stream
6. Review posts → Copy All to clipboard

**Architecture (local dev):**
```
Browser :5173 ──Vite proxy──→ FastAPI :8080
                                 ├── /api/* (REST + SSE streams)
                                 ├── Gemini API (brand analysis, content creation, review)
                                 ├── Cloud Firestore (brand profiles, plans, posts)
                                 └── Cloud Storage (generated images)
```

---

## Part 2: Production Deployment — Cloud Build CI/CD (Recommended)

The recommended deployment method uses `scripts/deploy.sh` which triggers a Cloud Build pipeline defined in `cloudbuild.yaml`. This is a **one-command deploy** that builds the Docker image with Firebase config baked in, pushes to Artifact Registry, and deploys to Cloud Run.

### 2.1 Architecture

```
deploy.sh → Cloud Build (cloudbuild.yaml)
               ├── Step 1: Docker build (with VITE_FIREBASE_* build args)
               ├── Step 2: Push to Artifact Registry
               └── Step 3: Deploy to Cloud Run (with runtime env vars)

Internet → Cloud Run :8080
             ├── /api/*         → FastAPI routes + SSE streams
             ├── /assets/*      → Static assets (JS, CSS, images)
             └── /* (catch-all) → index.html (SPA routing)
```

### 2.2 Setup

**One-time GCP setup:**

```bash
export PROJECT_ID=your-gcp-project-id
gcloud config set project $PROJECT_ID

# Enable required APIs
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  firestore.googleapis.com \
  storage.googleapis.com \
  artifactregistry.googleapis.com

# Create Artifact Registry repo
gcloud artifacts repositories create amplifi \
  --repository-format=docker \
  --location=us-central1

# Create Firestore database
gcloud firestore databases create --location=nam5 --type=firestore-native

# Create Cloud Storage bucket
gcloud storage buckets create gs://$PROJECT_ID-amplifi-assets \
  --location=us-central1 \
  --uniform-bucket-level-access

# Grant Firestore access to Cloud Run service account
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format='value(projectNumber)')
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$PROJECT_NUMBER-compute@developer.gserviceaccount.com" \
  --role="roles/datastore.user"

# Grant Logs Writer to see Cloud Build logs (required for CLOUD_LOGGING_ONLY mode)
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$PROJECT_NUMBER-compute@developer.gserviceaccount.com" \
  --role="roles/logging.logWriter"
```

### 2.3 Configure `.env`

Copy `.env.example` to `.env` in the **repo root** and fill in all values:

```env
# GCP project
GCP_PROJECT_ID=your-gcp-project-id
GCP_REGION=us-central1

# Gemini API key (server-side, set as Cloud Run env var)
GOOGLE_API_KEY=your-gemini-api-key

# CORS origin (your Cloud Run URL)
CORS_ORIGINS=https://amplifi-xxxxx-uc.a.run.app

# Firebase config (client-side, baked into JS bundle at build time)
VITE_FIREBASE_API_KEY=your-firebase-api-key
VITE_FIREBASE_AUTH_DOMAIN=your-project.firebaseapp.com
VITE_FIREBASE_PROJECT_ID=your-firebase-project-id
VITE_FIREBASE_STORAGE_BUCKET=your-project.firebasestorage.app
VITE_FIREBASE_MESSAGING_SENDER_ID=your-sender-id
VITE_FIREBASE_APP_ID=your-app-id

# Notion integration (optional)
NOTION_CLIENT_ID=your-notion-client-id
NOTION_CLIENT_SECRET=your-notion-client-secret
NOTION_REDIRECT_URI=https://your-cloud-run-url/auth/notion/callback

# Token encryption for Notion OAuth tokens (Fernet)
# Generate: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
TOKEN_ENCRYPT_KEY=your-fernet-key

# Resend email (optional)
RESEND_API_KEY=your-resend-api-key
```

> **Never commit `.env`** — it contains secrets. It's already in `.gitignore`.

### 2.4 Deploy

```bash
./scripts/deploy.sh
```

This single command:
1. Reads all config from `.env`
2. Validates required variables
3. Submits a Cloud Build job with substitutions
4. Cloud Build builds the Docker image (with `VITE_FIREBASE_*` as build args)
5. Pushes the image to Artifact Registry
6. Deploys to Cloud Run with all runtime env vars (`GOOGLE_API_KEY`, `CORS_ORIGINS`, `RESEND_API_KEY`, `NOTION_*`, `TOKEN_ENCRYPT_KEY`, `GEMINI_MODEL`)
7. Prints the live URL

### 2.5 Cloud Build Pipeline Details

The `cloudbuild.yaml` defines a 3-step pipeline:

| Step | What | Key Details |
|------|------|-------------|
| 1. Docker Build | Builds multi-stage image | Firebase `VITE_*` vars passed as `--build-arg` (baked into JS bundle) |
| 2. Push | Pushes to Artifact Registry | `{region}-docker.pkg.dev/{project}/amplifi/amplifi:latest` |
| 3. Deploy | Deploys to Cloud Run | Runtime env vars: `GOOGLE_API_KEY`, `CORS_ORIGINS`, `RESEND_API_KEY`, `NOTION_*`, `TOKEN_ENCRYPT_KEY`, `GEMINI_MODEL` |

**Build-time vs runtime env vars:**
- **Build-time** (`--build-arg`): `VITE_FIREBASE_*` — baked into the JS bundle by Vite, cannot be changed after build
- **Runtime** (`--update-env-vars`): `GOOGLE_API_KEY`, `CORS_ORIGINS`, `RESEND_API_KEY`, `NOTION_*`, `TOKEN_ENCRYPT_KEY`, `GEMINI_MODEL` — read by the Python backend at startup. Uses `--update-env-vars` (not `--set-env-vars`) to preserve any existing env vars on the Cloud Run service

### 2.6 Post-Deploy: Firebase Auth Domain

After your first deploy, add your Cloud Run URL to Firebase's authorized domains:
1. Go to [Firebase Console](https://console.firebase.google.com) → Authentication → Settings → Authorized domains
2. Add your Cloud Run domain (e.g., `amplifi-xxxxx-uc.a.run.app`)

### 2.7 SPA Routing

The backend serves the React SPA with a catch-all route. All deep links (e.g., `/brands`, `/dashboard/xyz`, `/auth/notion/callback`) are handled by serving `index.html` and letting React Router resolve the route client-side. Static assets under `/assets/` are served directly.

---

## Part 3: Production Deployment (Cloud Run) — Manual

If you prefer manual deployment without the CI/CD pipeline:

### 3.1 Build the Docker Image

From the **repo root**:

```bash
docker build -f backend/Dockerfile -t amplifi .
```

**What the Dockerfile does:**
1. Base: `python:3.12-slim`
2. Installs system deps: `build-essential`, `curl`, `ffmpeg`, Node.js 20
3. Copies `frontend/` → runs `npm ci && npm run build` (TypeScript compile + Vite build)
4. Installs Python deps from `backend/requirements.txt`
5. Copies `backend/`
6. Runs `uvicorn backend.server:app` on port 8080

### 3.2 Deploy to Cloud Run

```bash
export PROJECT_ID=your-gcp-project-id
export IMAGE=us-central1-docker.pkg.dev/$PROJECT_ID/amplifi/amplifi:latest
gcloud builds submit --tag $IMAGE --timeout=900

gcloud run deploy amplifi \
  --image $IMAGE \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --port 8080 \
  --memory 2Gi \
  --cpu 2 \
  --min-instances 0 \
  --max-instances 10 \
  --timeout 300 \
  --update-env-vars="GOOGLE_API_KEY=your-key,GCP_PROJECT_ID=$PROJECT_ID,GCS_BUCKET_NAME=$PROJECT_ID-amplifi-assets,CORS_ORIGINS=https://your-url.run.app,GEMINI_MODEL=gemini-3-flash-preview"
```

**Critical flags:**
- `--memory 2Gi` — Gemini interleaved generation (text+image) responses can be large
- `--timeout 300` — SSE content generation streams can run 2-3 minutes for a full 7-day plan
- `--port 8080` — Matches Dockerfile
- `CORS_ORIGINS` — Set to your Cloud Run URL after first deploy

### 3.3 Cloud Storage CORS (Required for Image Display)

```bash
cat > cors.json << 'EOF'
[
  {
    "origin": ["https://your-cloud-run-url.run.app", "http://localhost:5173"],
    "method": ["GET"],
    "responseHeader": ["Content-Type"],
    "maxAgeSeconds": 3600
  }
]
EOF

gcloud storage buckets update gs://$PROJECT_ID-amplifi-assets --cors-file=cors.json
```

---

## Part 4: Environment Variable Reference

### Server-Side (Runtime)

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GOOGLE_API_KEY` | Yes | `""` | Gemini API key for all agents |
| `GCP_PROJECT_ID` | Yes | — | GCP project ID |
| `GCS_BUCKET_NAME` | Yes | `{project}-amplifi-assets` | Cloud Storage bucket for images/video |
| `CORS_ORIGINS` | Yes | `http://localhost:5173` | Comma-separated allowed origins |
| `GEMINI_MODEL` | No | `gemini-3-flash-preview` | Default Gemini model |
| `RESEND_API_KEY` | No | `""` | Resend API key for email delivery (.ics calendar) |
| `NOTION_CLIENT_ID` | No | `""` | Notion OAuth client ID |
| `NOTION_CLIENT_SECRET` | No | `""` | Notion OAuth client secret |
| `NOTION_REDIRECT_URI` | Yes (if Notion) | — | Notion OAuth redirect URI — **no default**, must be set explicitly (e.g., `https://your-url.run.app/auth/notion/callback`) |
| `TOKEN_ENCRYPT_KEY` | No | — | Fernet encryption key for Notion OAuth tokens. Without it, tokens stored as plaintext (warning logged). Generate: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |

### Client-Side (Build-Time)

| Variable | Required | Description |
|----------|----------|-------------|
| `VITE_FIREBASE_API_KEY` | Yes | Firebase web API key |
| `VITE_FIREBASE_AUTH_DOMAIN` | Yes | Firebase auth domain |
| `VITE_FIREBASE_PROJECT_ID` | Yes | Firebase project ID |
| `VITE_FIREBASE_STORAGE_BUCKET` | Yes | Firebase storage bucket |
| `VITE_FIREBASE_MESSAGING_SENDER_ID` | Yes | Firebase messaging sender ID |
| `VITE_FIREBASE_APP_ID` | Yes | Firebase app ID |

> **Note:** `VITE_*` variables are baked into the JS bundle at build time by Vite. They must be passed as Docker `--build-arg` flags (handled automatically by `deploy.sh` and `cloudbuild.yaml`).

### Budget Constants (hardcoded in `config.py`)

| Constant | Value | Description |
|----------|-------|-------------|
| `IMAGE_COST_PER_UNIT` | $0.039 | Per generated image |
| `VIDEO_COST_FAST` | $1.20 | Per 8-sec Veo Fast clip |
| `VIDEO_COST_STD` | $3.20 | Per 8-sec Veo Standard clip |
| `TOTAL_BUDGET` | $100 | Per-session budget cap |
| `IMAGE_BUDGET` | $70 | Image generation cap |
| `VIDEO_BUDGET` | $30 | Video generation cap |

---

## Part 5: Project Structure

```
amplifi-hackaton/
├── backend/
│   ├── agents/
│   │   ├── brand_analyst.py          # URL scraping + brand DNA extraction
│   │   ├── strategy_agent.py         # 7-day content calendar + pillar strategy
│   │   ├── content_creator.py        # Gemini interleaved text+image generation
│   │   ├── review_agent.py           # Brand alignment review + revised captions
│   │   ├── social_voice_agent.py     # Platform voice analysis (LinkedIn/IG/X)
│   │   ├── voice_coach.py            # Gemini Live voice coaching
│   │   ├── video_creator.py          # Veo 3.1 video generation
│   │   └── video_repurpose_agent.py  # Video clip repurposing
│   ├── models/
│   │   ├── brand.py                  # BrandProfile Pydantic model
│   │   ├── plan.py                   # ContentPlan + DayBrief models
│   │   ├── post.py                   # Post model (caption, image, status)
│   │   └── api.py                    # Request/response schemas
│   ├── services/
│   │   ├── firestore_client.py       # Firestore CRUD for brands, plans, posts
│   │   ├── storage_client.py         # GCS upload/download for images
│   │   └── budget_tracker.py         # Per-session cost tracking
│   ├── tools/
│   │   ├── web_scraper.py            # httpx + BeautifulSoup URL crawling
│   │   └── brand_tools.py            # ADK tool wrappers for brand analysis
│   ├── server.py                     # FastAPI app setup + router includes (REST + SSE + SPA catch-all)
│   ├── config.py                     # Environment config + budget constants
│   ├── platforms.py                  # Platform Registry (10 platforms)
│   ├── Dockerfile                    # Multi-stage: Node build + Python runtime
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── pages/                    # Route-level page components
│   │   │   ├── LandingPage.tsx       # Marketing landing page (hero, features, CTA)
│   │   │   ├── BrandsPage.tsx        # Brand list with pagination + "Create" CTA
│   │   │   ├── OnboardPage.tsx       # Brand creation wizard
│   │   │   ├── DashboardPage.tsx     # Brand dashboard (calendar, posts, export)
│   │   │   ├── GeneratePage.tsx      # Per-day content generation with SSE
│   │   │   ├── EditBrandPage.tsx     # Brand profile editor + asset management
│   │   │   ├── ExportPage.tsx        # Bulk export (ZIP, Notion, .ics)
│   │   │   ├── NotionCallbackPage.tsx # Notion OAuth callback handler
│   │   │   ├── TermsPage.tsx         # Terms of Service
│   │   │   └── PrivacyPage.tsx       # Privacy Policy
│   │   ├── components/               # Reusable UI components
│   │   │   ├── NavBar.tsx            # Top nav (Home, My Brands/Get Started, Export, Account)
│   │   │   ├── PostCard.tsx          # Individual post display
│   │   │   ├── PostGenerator.tsx     # SSE streaming post generation
│   │   │   ├── PostLibrary.tsx       # Post list with "Copy All" clipboard
│   │   │   ├── ReviewPanel.tsx       # AI review scores and suggestions
│   │   │   ├── ContentCalendar.tsx   # 7-day calendar grid
│   │   │   ├── EventsInput.tsx       # Business events input
│   │   │   ├── BrandProfileCard.tsx  # Brand profile display
│   │   │   ├── BrandSummaryBar.tsx   # Compact brand info bar
│   │   │   ├── PlatformPreview.tsx   # Platform-specific post preview
│   │   │   ├── VoiceCoach.tsx        # Gemini Live voice coaching UI
│   │   │   ├── VideoRepurpose.tsx    # Video generation controls
│   │   │   ├── IntegrationConnect.tsx # Notion/email integration UI
│   │   │   └── SocialConnect.tsx     # Social platform OAuth (future)
│   │   ├── hooks/
│   │   │   └── useAuth.ts           # Firebase Google Auth hook
│   │   ├── api/
│   │   │   ├── client.ts            # API client (REST calls to backend)
│   │   │   └── firebase.ts          # Firebase config + Google Sign-In
│   │   ├── theme.ts                 # Design system tokens (colors, spacing)
│   │   └── App.tsx                  # Router (/, /brands, /onboard, /dashboard/:id, ...)
│   ├── package.json                 # React 19 + react-router-dom + Vite 7
│   ├── tsconfig.json                # TypeScript config
│   ├── vite.config.ts               # Proxy /api → :8080
│   └── index.html
├── scripts/
│   └── deploy.sh                    # One-command Cloud Build deploy
├── cloudbuild.yaml                  # Cloud Build CI/CD pipeline (3 steps)
├── terraform/                       # Infrastructure as Code (Part 6)
│   ├── main.tf
│   ├── variables.tf
│   └── terraform.tfvars.example
├── .env.example                     # Root-level deploy config template
├── .env                             # Local deploy config (gitignored)
└── docs/
    ├── PRD.md
    ├── TDD.md
    ├── DEPLOYMENT.md                # This file
    ├── architecture.mermaid
    ├── amplifi-ui.jsx
    └── playtest-personas.md
```

---

## Part 6: Automated Deployment (Terraform)

> **Hackathon bonus:** This section demonstrates automated cloud deployment using infrastructure-as-code.

Instead of running the manual `gcloud` commands, you can provision everything with a single `terraform apply`. The Terraform config in `terraform/` creates:

- All required GCP API enablements
- Cloud Firestore database
- Cloud Storage bucket with CORS policy
- Artifact Registry repository
- Cloud Run service with 300s SSE timeout
- Public IAM policy (unauthenticated access)

### 6.1 Prerequisites

Install Terraform (v1.5+):

```bash
# macOS
brew install terraform

# Linux
sudo apt-get install -y terraform

# Or download from https://developer.hashicorp.com/terraform/downloads
```

Authenticate with GCP:

```bash
gcloud auth application-default login
```

### 6.2 Configure Variables

```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars
```

Edit `terraform.tfvars`:

```hcl
project_id     = "your-gcp-project-id"
region         = "us-central1"
gemini_api_key = "your-gemini-api-key"
```

> **Never commit `terraform.tfvars`** — it contains your API key. It's already in `.gitignore`.

### 6.3 Deploy Everything

```bash
cd terraform
terraform init
terraform plan     # Review what will be created
terraform apply    # Provision all resources
```

Terraform outputs your Cloud Run URL:

```
Outputs:

service_url        = "https://amplifi-abc123-uc.a.run.app"
image_url          = "us-central1-docker.pkg.dev/your-project/amplifi/amplifi:latest"
bucket_name        = "your-project-amplifi-assets"
firestore_database = "(default)"
```

### 6.4 Tear Down (if needed)

```bash
terraform destroy   # Removes all provisioned resources
```

### 6.5 What's in `terraform/`

| File | Purpose |
|------|---------|
| `main.tf` | All resource definitions (APIs, Firestore, GCS bucket, Artifact Registry, Cloud Run, IAM) |
| `variables.tf` | Input variables (project_id, region, gemini_api_key) |
| `terraform.tfvars.example` | Template for your secret values |

---

## Part 7: Security

### 7.1 Authentication Flow

All API requests require a Firebase ID token in the `Authorization: Bearer <token>` header. The backend verifies tokens using the **Firebase Admin SDK** (`firebase_admin`).

**How it works:**
1. Frontend signs in via Firebase Google Sign-In and obtains an ID token
2. Every API call includes `Authorization: Bearer <id_token>` header
3. Backend auth middleware verifies the token using `firebase_admin.auth.verify_id_token()`
4. Verified user UID is attached to the request for downstream use (Firestore scoping, etc.)

**Credentials:**
- **Cloud Run (production):** Uses Application Default Credentials (ADC) automatically — no service account key file needed. The Cloud Run service account is auto-detected by the Firebase Admin SDK.
- **Local development:** Uses `gcloud auth application-default login` credentials (already set up in Part 1).
- **No new env var needed** for Firebase Admin SDK — it discovers credentials via ADC.

### 7.2 Notion Token Encryption

Notion OAuth access tokens are encrypted at rest in Firestore using **Fernet symmetric encryption** (AES-128-CBC via the `cryptography` package).

| Component | Details |
|-----------|---------|
| Algorithm | Fernet (AES-128-CBC + HMAC-SHA256) |
| Key env var | `TOKEN_ENCRYPT_KEY` |
| Key generation | `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| Fallback | If `TOKEN_ENCRYPT_KEY` is not set, tokens are stored as plaintext with a warning log |

**Important:** Once tokens are encrypted with a key, changing or losing that key makes existing stored tokens unreadable. Back up the key securely.

### 7.3 CORS

CORS is configured via the `CORS_ORIGINS` env var. The backend uses `allow_headers=["*"]` which permits the `Authorization` header needed for Firebase auth. In production, set `CORS_ORIGINS` to your exact Cloud Run URL (not `*`).

---

## Troubleshooting

| Issue | Cause | Fix |
|-------|-------|-----|
| `CORS error` in browser | `CORS_ORIGINS` doesn't include your frontend URL | Update `CORS_ORIGINS` env var (comma-separated) |
| SSE stream hangs / times out | Cloud Run default timeout too short | Deploy with `--timeout 300` |
| `ModuleNotFoundError: google.adk` | Missing ADK dependency | `pip install google-adk==0.5.0` |
| Images not loading from GCS | Bucket CORS not configured | Set GCS CORS policy (see §3.3) or use Terraform (auto-configured) |
| Cloud Build logs empty / invisible | Service account missing Logs Writer role | Grant `roles/logging.logWriter` to the compute service account (see §2.2) |
| `tsc -b` fails during Docker build | TypeScript compilation errors | Run `cd frontend && npm run build` locally first to catch errors |
| `ffmpeg not found` locally | ffmpeg not installed on host | `brew install ffmpeg` (macOS) or `sudo apt install ffmpeg` (Linux) — only needed for video features |
| Brand analysis returns empty | URL not crawlable / description too short | Use "describe your business" with 2-3 sentences minimum |
| Budget exceeded error | Session hit $100 cap | Budget resets per session; reduce image count or use caption-only mode |
| `npm ci` fails in Docker | `package-lock.json` out of sync | Run `cd frontend && npm install` locally to regenerate lockfile, commit |
| `terraform plan` fails with auth error | Not authenticated with GCP | Run `gcloud auth application-default login` |
| `terraform apply` — image not found | Docker image not pushed yet | Build and push the image first (see §6.3), then `terraform apply` |
| Google Sign-In popup blocked | Cloud Run URL not in Firebase authorized domains | Add your Cloud Run domain in Firebase Console → Auth → Settings → Authorized domains |
| Firestore `permission denied` (403) | Cloud Run service account missing role | Grant `roles/datastore.user` to the compute service account (see §2.2) |
| SPA routes return 404 | Backend not serving `index.html` for deep links | Backend uses catch-all route — ensure you're on the latest `server.py` |
| Notion OAuth callback 404 | Same as SPA routing issue | Backend catch-all serves `index.html` for `/auth/notion/callback` |
| `401 Unauthorized` on all API calls | Firebase ID token missing or invalid | Ensure frontend sends `Authorization: Bearer <token>` header; check that Firebase project IDs match between frontend and backend |
| `TOKEN_ENCRYPT_KEY` warning in logs | Env var not set | Generate a Fernet key and set `TOKEN_ENCRYPT_KEY` — tokens will be stored as plaintext until set |
| Notion tokens unreadable after redeploy | `TOKEN_ENCRYPT_KEY` changed or lost | Tokens encrypted with the old key cannot be decrypted; users must re-authorize Notion |
| `NOTION_REDIRECT_URI` not set error | No default fallback | Set `NOTION_REDIRECT_URI` explicitly in `.env` (e.g., `https://your-url.run.app/auth/notion/callback`) |

---

## Key Differences from Fireside

| Aspect | Fireside | Amplispark |
|--------|----------|---------|
| Backend entry | `backend/main.py` | `backend/server.py` |
| Backend port | 8000 | 8080 |
| Python version | 3.11 | 3.12 |
| Frontend language | JavaScript (JSX) | TypeScript (TSX) |
| React version | 18 | 19 |
| Vite version | 5 | 7 |
| Real-time | WebSocket | SSE (Server-Sent Events) |
| Auth | None (anonymous) | Firebase Google Sign-In |
| Agent framework | Direct Gemini API calls | Google ADK pipeline |
| External storage | Firestore only | Firestore + Cloud Storage |
| Dockerfile scope | Backend only | Full-stack (Node build + Python) |
| CI/CD | Manual deploy | Cloud Build + deploy.sh |
| Terraform extras | Firestore + Cloud Run | Firestore + GCS bucket + Cloud Run |
