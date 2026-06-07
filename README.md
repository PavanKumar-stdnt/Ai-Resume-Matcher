# 🎯 AI Resume Matcher v2

> **Production-grade True RAG pipeline** — resumes are chunked, embedded locally, retrieved semantically, and evaluated by Gemini AI. Batch-match up to 20 resumes against a single job description.

---

## 📋 Table of Contents

- [Overview](#overview)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Features](#features)
- [Local Setup](#local-setup)
- [Docker Setup](#docker-setup)
- [Running with Docker Compose](#running-with-docker-compose)
- [Deployment — AWS EC2](#deployment--aws-ec2)
- [Deployment — Render](#deployment--render)
- [Deployment — Streamlit Cloud](#deployment--streamlit-cloud)
- [CI/CD — GitHub Actions](#cicd--github-actions)
- [MLflow Tracking](#mlflow-tracking)
- [API Reference](#api-reference)
- [Environment Variables](#environment-variables)
- [Scoring System](#scoring-system)

---

## Overview

AI Resume Matcher is a **framework-free**, production-ready resume screening system built without LangChain, LlamaIndex, or any AI orchestration framework. It implements a **true RAG (Retrieval-Augmented Generation)** pipeline where:

1. Resume text is **chunked** into overlapping 400-word windows
2. Each chunk is **embedded** locally using FastEmbed (BAAI/bge-small-en-v1.5) — zero API cost
3. The most **relevant chunks are retrieved** from Qdrant Cloud using the job description as the query
4. Google **Gemini 2.5 Flash evaluates only the retrieved chunks** — not the full document
5. A **weighted composite score** (35% vector + 65% LLM) ranks the match

```
Resume File → Parse → Chunk → Embed → Index in Qdrant
                                              ↓
Job Description ──────────────────→ Retrieve Top-K Chunks
                                              ↓
                              Gemini evaluates retrieved chunks
                                              ↓
                              Score (0-100) + Analysis + MLflow log
```

---

## Tech Stack

| Layer | Tool | Version |
|---|---|---|
| **Backend** | FastAPI + Uvicorn | 0.115.6 / 0.32.1 |
| **Frontend** | Streamlit | 1.41.1 |
| **Vector DB** | Qdrant Cloud | qdrant-client 1.13.3 |
| **Embeddings** | FastEmbed (BAAI/bge-small-en-v1.5) | 0.4.2 |
| **LLM** | Google Gemini 2.5 Flash | google-genai 1.5.0 |
| **Tracking** | MLflow | 2.14.1 |
| **PDF Parser** | pypdf | 5.1.0 |
| **DOCX Parser** | python-docx | 1.1.2 |
| **Settings** | Pydantic-Settings | 2.6.1 |
| **Containers** | Docker + Docker Compose | multi-stage |
| **CI/CD** | GitHub Actions | GHCR registry |

---

## Project Structure

```
ai-resume-matcher/
│
├── 📄 streamlit_app.py              # Streamlit Cloud entry point
├── 📄 requirements-prod.txt         # Backend dependencies (pinned)
├── 📄 requirements-streamlit.txt    # Frontend dependencies only
├── 📄 Dockerfile                    # Multi-stage FastAPI image
├── 📄 Dockerfile.mlflow             # MLflow server image
├── 📄 docker-compose.yml            # Full stack orchestration
├── 📄 render.yaml                   # Render.com blueprint
├── 📄 ec2-setup.sh                  # EC2 bootstrap script
├── 📄 .env.example                  # Environment variable template
├── 📄 .dockerignore                 # Docker build exclusions
│
├── 📁 .github/
│   └── workflows/
│       └── ci-cd.yml                # GitHub Actions pipeline
│
├── 📁 .streamlit/
│   ├── config.toml                  # Streamlit theme config
│   └── secrets.toml                 # Local secrets (git ignored)
│
├── 📁 mlflow/
│   └── mlflow-compose.yml           # Standalone MLflow compose
│
└── 📁 src/
    ├── config.py                    # Pydantic-Settings (crash on missing vars)
    ├── main.py                      # FastAPI app factory + startup
    │
    ├── api/
    │   ├── dependencies.py          # X-API-KEY security (hmac.compare_digest)
    │   └── endpoints.py             # Routes: /match, /match/batch, /history
    │
    ├── core/
    │   ├── utils.py                 # PDF/DOCX/TXT parsers + chunking engine
    │   └── logger.py                # Thread-safe CSV history logger
    │
    ├── services/
    │   ├── vector_service.py        # Qdrant Cloud: index + retrieve + delete
    │   ├── llm_service.py           # Gemini RAG prompt builder + caller
    │   ├── orchestrator.py          # 4-stage pipeline + batch runner
    │   └── mlflow_tracker.py        # MLflow experiment tracker
    │
    └── ui/
        └── dashboard.py             # Streamlit dark UI + batch leaderboard
```

---

## Features

- ✅ **True RAG** — LLM sees only retrieved chunks, not full document
- ✅ **Sentence-aware chunking** — 400-word windows, 80-word overlap, never cuts mid-sentence
- ✅ **Batch matching** — upload up to 20 resumes, set JD once, get ranked leaderboard
- ✅ **Local CPU embeddings** — FastEmbed runs inside Docker, zero API cost
- ✅ **MLflow tracking** — every run logged with params, metrics, and artifacts
- ✅ **Thread-safe CSV history** — append-only match history with threading.Lock
- ✅ **Constant-time auth** — hmac.compare_digest prevents timing attacks
- ✅ **Crash-on-startup** — Pydantic-Settings validates all env vars before serving
- ✅ **Multi-format parsing** — PDF, DOCX, TXT with encoding fallback chain
- ✅ **Docker multi-stage** — 680MB runtime image vs 2.1GB single-stage

---

## Local Setup

### Prerequisites

- Python 3.10 or higher
- A Google Gemini API key → [aistudio.google.com](https://aistudio.google.com)
- A Qdrant Cloud account → [cloud.qdrant.io](https://cloud.qdrant.io) (free tier)

### Step 1 — Clone the Repository

```bash
git clone https://github.com/YOUR_USERNAME/ai-resume-matcher.git
cd ai-resume-matcher
```

### Step 2 — Create Virtual Environment

```bash
# Create
python -m venv venv

# Activate — Windows
venv\Scripts\activate

# Activate — Mac/Linux
source venv/bin/activate
```

### Step 3 — Install Dependencies

```bash
pip install -r requirements-prod.txt
```

### Step 4 — Configure Environment Variables

```bash
cp .env.example .env
```

Open `.env` and fill in all values:

```env
# ── Required ───────────────────────────────────────────
GOOGLE_API_KEY=AIzaSy_your_real_key_here
API_SECRET_KEY=your_strong_random_secret_here

# ── Qdrant Cloud ───────────────────────────────────────
QDRANT_URL=https://xxxx.qdrant.io:6333
QDRANT_API_KEY=your_qdrant_api_key
QDRANT_COLLECTION_NAME=resumes

# ── Server ─────────────────────────────────────────────
HOST=0.0.0.0
PORT=8000
ENVIRONMENT=development
ALLOWED_ORIGINS=*

# ── MLflow ─────────────────────────────────────────────
MLFLOW_TRACKING_URI=./mlruns
MLFLOW_EXPERIMENT_NAME=ai-resume-matcher
MLFLOW_ENABLED=true

# ── Models ─────────────────────────────────────────────
GEMINI_MODEL=gemini-2.5-flash
EMBEDDING_MODEL=BAAI/bge-small-en-v1.5
EMBEDDING_DIMENSION=384
HISTORY_CSV_PATH=./matching_history_database.csv
```

> **Generate a strong API secret key:**
> ```bash
> python -c "import secrets; print(secrets.token_urlsafe(32))"
> ```

### Step 5 — Run Locally (Without Docker)

**Terminal 1 — Backend:**
```bash
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

**Terminal 2 — Dashboard:**
```bash
streamlit run streamlit_app.py
```

Visit:
- Dashboard → `http://localhost:8501`
- API Docs → `http://localhost:8000/docs`
- Health Check → `http://localhost:8000/api/v1/health`

---

## Docker Setup

### Prerequisites

- Docker Desktop installed → [docker.com/products/docker-desktop](https://www.docker.com/products/docker-desktop)
- Verify installation:

```bash
docker --version
# Docker version 26.x.x

docker compose version
# Docker Compose version v2.x.x
```

### Build Docker Images

**Build the FastAPI backend image:**

```bash
docker build -t resume-matcher-api:latest .
```

Expected output:
```
[+] Building 48.3s
 => [builder 1/5] FROM python:3.11-slim          3.2s
 => [builder 2/5] RUN apt-get update             8.1s
 => [builder 3/5] COPY requirements*.txt         0.1s
 => [builder 4/5] RUN pip install               31.4s
 => [runtime 1/3] COPY --from=builder /install   2.1s
 => [runtime 2/3] COPY src/ ./src/               0.3s
 => exporting to image                           2.9s
 ✔ Successfully built resume-matcher-api:latest
```

**Build the MLflow server image:**

```bash
docker build -t resume-matcher-mlflow:latest -f Dockerfile.mlflow .
```

**Verify both images were created:**

```bash
docker images
```

Expected output:
```
REPOSITORY                TAG       SIZE
resume-matcher-api        latest    720MB
resume-matcher-mlflow     latest    480MB
```

---

## Running with Docker Compose

Docker Compose starts the API and MLflow together as a coordinated stack.

> **Note:** This project runs without Nginx for simplicity.
> The API is accessed directly on port 8000.

### Start the Full Stack

```bash
docker compose up -d
```

First run output (takes 3–5 minutes on first build):
```
[+] Running 5/5
 ✔ Network resume-net              Created
 ✔ Volume api_data                 Created
 ✔ Volume mlflow_data              Created
 ✔ Volume fastembed_cache          Created
 ✔ Container resume-matcher-mlflow Started
 ✔ Container resume-matcher-api    Started
```

### Verify Containers Are Running

```bash
docker compose ps
```

Expected output:
```
NAME                      STATUS          PORTS
resume-matcher-api        Up (healthy)    0.0.0.0:8000->8000/tcp
resume-matcher-mlflow     Up (healthy)    0.0.0.0:5000->5000/tcp
```

> Both containers must show **Up (healthy)** before use.

### Test the Running Stack

```bash
# Health check
curl http://localhost:8000/api/v1/health
# → {"status": "ok", "service": "AI Resume Matcher v2 — Production"}

# Test authentication (should return 403 without key)
curl http://localhost:8000/api/v1/history
# → {"detail": "Not authenticated"}

# Test with API key
curl -H "X-API-KEY: your_secret_key" http://localhost:8000/api/v1/history
# → {"count": 0, "records": []}
```

### View Live Logs

```bash
# All containers
docker compose logs -f

# API only
docker compose logs -f api

# MLflow only
docker compose logs -f mlflow

# Last 50 lines from API
docker compose logs --tail=50 api
```

### Start the Dashboard (Separate Terminal)

```bash
# Run Streamlit locally pointing to Dockerized API
streamlit run streamlit_app.py
```

In the sidebar:
```
API Base URL → http://localhost:8000
X-API-KEY    → your_secret_key_from_env
```

### Rebuild After Code Changes

```bash
# Rebuild and restart only the API container
docker compose up -d --build api

# Rebuild everything
docker compose up -d --build
```

### Open a Shell Inside the Container

```bash
# Debug the running API container
docker compose exec api bash

# Inside the container
ls /app/src/
python -c "import fastapi; print(fastapi.__version__)"
exit
```

### Stop the Stack

```bash
# Stop containers but keep data (volumes preserved)
docker compose down

# Stop and delete all volumes (removes all data)
docker compose down -v
```

### Useful Docker Commands

```bash
# View resource usage
docker stats

# Check disk usage
docker system df

# Remove unused images
docker image prune -f

# Remove stopped containers
docker container prune -f

# Full cleanup (careful — removes everything unused)
docker system prune -f
```

---

## Deployment — AWS EC2

### Step 1 — Launch EC2 Instance

```
AWS Console → EC2 → Launch Instance

Settings:
  Name:           ai-resume-matcher
  AMI:            Ubuntu Server 22.04 LTS
  Instance type:  t3.medium (minimum) or t3.large (recommended)
  Key pair:       Create new → download .pem file
  Security group: Allow inbound ports:
                    22   (SSH)
                    8000 (API)
                    5000 (MLflow)
```

### Step 2 — SSH Into Your EC2 Instance

```bash
chmod 400 your-key.pem
ssh -i your-key.pem ubuntu@YOUR_EC2_PUBLIC_IP
```

### Step 3 — Run Bootstrap Script

```bash
# Download and run the one-time setup script
curl -O https://raw.githubusercontent.com/YOUR_USERNAME/ai-resume-matcher/main/ec2-setup.sh
chmod +x ec2-setup.sh
sudo ./ec2-setup.sh
```

This script automatically installs:
- Docker and Docker Compose
- Git, curl, htop
- UFW firewall rules
- Systemd service for auto-restart on reboot

Verify Docker is installed:
```bash
docker --version
docker compose version
```

### Step 4 — Clone Repository and Configure

```bash
cd /opt/ai-resume-matcher
git clone https://github.com/YOUR_USERNAME/ai-resume-matcher.git .
cp .env.example .env
nano .env
# Fill in all values — same as your local .env
```

### Step 5 — Build and Start Docker Stack

```bash
# Build images and start all containers
docker compose up -d --build
```

Wait 4–6 minutes for the first build (downloads FastEmbed model ~130MB).

```bash
# Watch startup logs
docker compose logs -f

# Verify all containers healthy
docker compose ps

# Test health
curl http://localhost:8000/api/v1/health
```

### Step 6 — Enable Auto-Start on Reboot

```bash
sudo systemctl enable resume-matcher.service
sudo systemctl start resume-matcher.service
sudo systemctl status resume-matcher.service
```

Now if EC2 reboots, Docker automatically restarts all containers.

### Step 7 — Update Deployment

```bash
cd /opt/ai-resume-matcher

# Pull latest code
git pull origin main

# Rebuild and restart API
docker compose up -d --build api

# Verify
curl http://localhost:8000/api/v1/health
```

### Access Points on EC2

```
API:    http://YOUR_EC2_IP:8000
Docs:   http://YOUR_EC2_IP:8000/docs
MLflow: http://YOUR_EC2_IP:5000
```

---

## Deployment — Render

> **Recommended for simplicity** — Render reads your Dockerfile and render.yaml automatically. No server management required.

### Step 1 — Create a Render Account

```
1. Go to → https://render.com
2. Sign up with your GitHub account
3. Authorize Render to access your repositories
```

### Step 2 — Deploy via Blueprint

```
1. Click → New + → Blueprint
2. Connect → select your ai-resume-matcher repository
3. Render automatically reads render.yaml
4. Click → Apply
```

Two services are created automatically:
```
resume-matcher-api     → FastAPI backend (port 8000)
resume-matcher-mlflow  → MLflow tracking server (port 5000)
```

### Step 3 — Set Environment Variables

Click `resume-matcher-api` → **Environment** tab → add each variable:

| Key | Value |
|---|---|
| `GOOGLE_API_KEY` | Your Gemini API key |
| `API_SECRET_KEY` | Your strong random secret |
| `QDRANT_URL` | Your Qdrant Cloud cluster URL |
| `QDRANT_API_KEY` | Your Qdrant Cloud API key |

Click **Save Changes** → Render deploys automatically.

### Step 4 — Get Your Deploy Hook URL

```
Render dashboard → resume-matcher-api
→ Settings → Deploy Hook → Copy URL
```

Save this URL — you will add it as a GitHub Secret for CI/CD.

### Step 5 — Verify Deployment

```
Visit:
https://resume-matcher-api.onrender.com/api/v1/health
→ {"status": "ok", "service": "AI Resume Matcher v2 — Production"}

API Docs:
https://resume-matcher-api.onrender.com/docs

MLflow:
https://resume-matcher-mlflow.onrender.com
```

### Render Free Tier Notes

```
• App sleeps after 15 minutes of inactivity
• Wakes up automatically on first request (~30 seconds)
• 750 hours/month free (enough for 1 service 24/7)
• Upgrade to Starter ($7/month) to disable sleep
```

### Update Deployment on Render

```bash
# Any push to main branch auto-deploys via render.yaml
git add .
git commit -m "update: your change"
git push origin main
# → Render detects push and auto-deploys
```

---

## Deployment — Streamlit Cloud

> The frontend dashboard is deployed separately on Streamlit Cloud.
> It calls the Render/EC2 backend over HTTPS.

### Step 1 — Create a Streamlit Account

```
1. Go to → https://share.streamlit.io
2. Sign in with GitHub
```

### Step 2 — Deploy Your App

```
1. Click → New app
2. Fill in:
     Repository:       YOUR_USERNAME/ai-resume-matcher
     Branch:           main
     Main file path:   streamlit_app.py
     Requirements:     requirements-streamlit.txt
3. Click → Advanced settings
```

### Step 3 — Add Secrets

In **Advanced settings → Secrets**, paste exactly:

```toml
API_BASE_URL = "https://resume-matcher-api.onrender.com"
API_SECRET_KEY = "your_strong_random_secret_here"
```

> The `API_SECRET_KEY` here must **exactly match** the value you set in Render/EC2.

### Step 4 — Deploy

```
Click → Deploy!
Wait 2–3 minutes for the app to build.

Your live URL:
https://YOUR_USERNAME-ai-resume-matcher-xxxx.streamlit.app
```

### Step 5 — Verify

Open your Streamlit URL. The sidebar auto-fills from secrets:
```
API Base URL → https://resume-matcher-api.onrender.com
X-API-KEY    → (loaded from secrets — hidden)
```

Run a test match to confirm end-to-end connectivity.

### Updating Streamlit App

```bash
# Any push to main branch auto-redeploys
git push origin main
# → Streamlit Cloud detects the push and rebuilds
```

### Streamlit Free Tier Notes

```
• 1 public app free forever
• 1GB RAM limit
• Unlimited traffic
• Custom domain available on paid plans
```

---

## CI/CD — GitHub Actions

Every push to the `main` branch automatically runs the full pipeline:

```
push to main
    │
    ├── lint (ruff + black)      ~1 min
    ├── test (pytest)            ~2 min
    ├── build (Docker → GHCR)   ~4 min
    └── deploy                  ~2 min
          ├── Render webhook  (if DEPLOY_TARGET=render)
          └── EC2 SSH deploy  (if DEPLOY_TARGET=ec2)
```

### Step 1 — Add GitHub Secrets

Go to your repository:
```
Settings → Secrets and variables → Actions → New repository secret
```

**For Render deployment, add:**

| Secret Name | Value |
|---|---|
| `RENDER_DEPLOY_HOOK_URL` | Copied from Render dashboard (Step 4 above) |

**For EC2 deployment, add:**

| Secret Name | Value |
|---|---|
| `EC2_HOST` | Your EC2 public IP address |
| `EC2_USER` | `ubuntu` |
| `EC2_SSH_KEY` | Full contents of your `.pem` private key file |

### Step 2 — Add GitHub Variable

```
Settings → Secrets and variables → Actions → Variables → New variable

Name:   DEPLOY_TARGET
Value:  render     ← if deploying to Render
        or
        ec2        ← if deploying to EC2
```

### Step 3 — Push to Trigger Pipeline

```bash
git add .
git commit -m "feat: trigger CI/CD pipeline"
git push origin main
```

Go to **GitHub → Actions tab** to watch the pipeline run.

### What Each Job Does

**Job 1 — Lint**
```bash
ruff check src/        # Checks for code errors and style issues
black --check src/     # Checks code formatting
```

**Job 2 — Test**
```bash
pytest tests/ -v --tb=short    # Runs unit tests
# Skips gracefully if no tests/ directory yet
```

**Job 3 — Build**
```bash
# Builds Docker image
docker build -t ghcr.io/YOUR_USERNAME/resume-matcher-api:latest .

# Pushes to GitHub Container Registry (GHCR)
docker push ghcr.io/YOUR_USERNAME/resume-matcher-api:latest
```

**Job 4A — Deploy to Render**
```bash
# Triggers Render deploy webhook
curl -X POST "$RENDER_DEPLOY_HOOK_URL"
```

**Job 4B — Deploy to EC2**
```bash
# SSH into EC2 and run these commands automatically:
docker login ghcr.io
docker compose pull api
docker compose up -d --no-deps api
sleep 20
curl -f http://localhost:8000/api/v1/health
docker image prune -f
```

### View Pipeline Results

```
GitHub → your repo → Actions tab

Each run shows:
✅ Lint & Format Check     (green = all code quality checks passed)
✅ Unit Tests              (green = all tests passed)
✅ Build & Push Image      (green = Docker image pushed to GHCR)
✅ Deploy to Production    (green = deployed successfully)
```

### paths-ignore — Smart Triggering

The pipeline only triggers on meaningful changes:

```yaml
on:
  push:
    paths-ignore:
      - '**.md'          # README changes don't trigger rebuild
      - '.streamlit/**'  # Streamlit config changes don't rebuild backend
```

---

## MLflow Tracking

Every match run is automatically logged to MLflow.

### Access MLflow UI

```
Render:  https://resume-matcher-mlflow.onrender.com
EC2:     http://YOUR_EC2_IP:5000
Local:   http://localhost:5000
```

### What Gets Tracked

```
Experiments → ai-resume-matcher
└── Runs (one per match request)
      ├── Parameters
      │     ├── embedding_model: BAAI/bge-small-en-v1.5
      │     ├── chunk_size: 400
      │     ├── chunk_overlap: 80
      │     ├── vector_weight: 0.35
      │     ├── llm_weight: 0.65
      │     └── job_description_snippet: ...
      ├── Metrics
      │     ├── vector_score: 72.4
      │     ├── llm_score: 85.0
      │     ├── final_score: 80.6
      │     ├── chunks_indexed: 8
      │     ├── chunks_retrieved: 5
      │     └── elapsed_seconds: 18.3
      └── Artifacts
            ├── retrieved_chunks/retrieved_chunks.json
            └── llm_analysis/llm_analysis.txt
```

### Disable MLflow (Optional)

```env
# In your .env file
MLFLOW_ENABLED=false
```

---

## API Reference

### Base URL

```
Local:   http://localhost:8000
Render:  https://resume-matcher-api.onrender.com
EC2:     http://YOUR_EC2_IP:8000
```

### Authentication

All routes except `/api/v1/health` require the `X-API-KEY` header:

```bash
curl -H "X-API-KEY: your_secret_key" http://localhost:8000/api/v1/history
```

---

### GET /api/v1/health

Public liveness check — no authentication required.

```bash
curl http://localhost:8000/api/v1/health
```

```json
{
  "status": "ok",
  "service": "AI Resume Matcher v2 — Production"
}
```

---

### POST /api/v1/match

Match a single resume against a job description using the full RAG pipeline.

```bash
curl -X POST http://localhost:8000/api/v1/match \
  -H "X-API-KEY: your_secret_key" \
  -F "resume_file=@/path/to/resume.pdf" \
  -F "job_description_text=We are looking for a Python developer..."
```

**Response:**
```json
{
  "resume_filename": "john_doe.pdf",
  "vector_score": 72.4,
  "llm_score": 85.0,
  "final_score": 80.6,
  "analysis": "The candidate demonstrates strong alignment...",
  "chunks_indexed": 8,
  "chunks_retrieved": 5,
  "retrieved_chunk_scores": [
    {"chunk_index": 2, "score": 88.4},
    {"chunk_index": 0, "score": 81.2},
    {"chunk_index": 5, "score": 76.9},
    {"chunk_index": 3, "score": 71.3},
    {"chunk_index": 1, "score": 68.1}
  ],
  "elapsed_seconds": 18.3,
  "warnings": [],
  "stages": {
    "parsing": true,
    "rag_indexing": true,
    "rag_retrieval": true,
    "llm_evaluation": true
  }
}
```

---

### POST /api/v1/match/batch

Match multiple resumes against a single job description. Results ranked by final_score.

```bash
curl -X POST http://localhost:8000/api/v1/match/batch \
  -H "X-API-KEY: your_secret_key" \
  -F "resume_files=@john_doe.pdf" \
  -F "resume_files=@jane_smith.pdf" \
  -F "resume_files=@alex_jones.pdf" \
  -F "job_description_text=We are looking for a Python developer..."
```

**Response:**
```json
{
  "total": 3,
  "successful": 3,
  "failed": 0,
  "job_description_snippet": "We are looking for a Python developer...",
  "results": [
    {
      "rank": 1,
      "resume_filename": "jane_smith.pdf",
      "final_score": 88.2,
      "vector_score": 79.1,
      "llm_score": 93.0
    },
    {
      "rank": 2,
      "resume_filename": "john_doe.pdf",
      "final_score": 80.6,
      "vector_score": 72.4,
      "llm_score": 85.0
    },
    {
      "rank": 3,
      "resume_filename": "alex_jones.pdf",
      "final_score": 61.3,
      "vector_score": 55.8,
      "llm_score": 64.4
    }
  ]
}
```

---

### GET /api/v1/history

Returns the most recent matching history from the CSV file.

```bash
curl -H "X-API-KEY: your_secret_key" \
     "http://localhost:8000/api/v1/history?limit=10"
```

```json
{
  "count": 10,
  "records": [
    {
      "timestamp_utc": "2025-06-01T14:32:11",
      "resume_filename": "john_doe.pdf",
      "vector_similarity_score": "72.4",
      "llm_analysis_score": "85.0",
      "final_score": "80.6"
    }
  ]
}
```

---

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `GOOGLE_API_KEY` | ✅ | — | Google Gemini API key |
| `API_SECRET_KEY` | ✅ | — | X-API-KEY header token (self-generated) |
| `QDRANT_URL` | ✅ | — | Qdrant Cloud cluster URL with port |
| `QDRANT_API_KEY` | ✅ | — | Qdrant Cloud API key |
| `QDRANT_COLLECTION_NAME` | Optional | `resumes` | Qdrant collection name |
| `HOST` | Optional | `0.0.0.0` | Server bind host |
| `PORT` | Optional | `8000` | Server bind port |
| `ENVIRONMENT` | Optional | `production` | `development` or `production` |
| `ALLOWED_ORIGINS` | Optional | `*` | Comma-separated CORS origins |
| `GEMINI_MODEL` | Optional | `gemini-2.5-flash` | Gemini model identifier |
| `EMBEDDING_MODEL` | Optional | `BAAI/bge-small-en-v1.5` | FastEmbed model |
| `EMBEDDING_DIMENSION` | Optional | `384` | Vector dimensions |
| `MLFLOW_TRACKING_URI` | Optional | `./mlruns` | MLflow server URL |
| `MLFLOW_EXPERIMENT_NAME` | Optional | `ai-resume-matcher` | MLflow experiment name |
| `MLFLOW_ENABLED` | Optional | `true` | Enable/disable MLflow tracking |
| `HISTORY_CSV_PATH` | Optional | `./matching_history_database.csv` | CSV history file path |

---

## Scoring System

### How Scores Are Calculated

```
final_score = (vector_score × 0.35) + (llm_score × 0.65)
```

**Vector Score (35%)** — Cosine similarity between resume chunks and job description using BAAI/bge-small-en-v1.5 embeddings. Mean of top-5 retrieved chunk scores. Range: 0–100.

**LLM Score (65%)** — Qualitative recruiter evaluation by Gemini across 5 dimensions:
1. Technical skills overlap
2. Domain expertise alignment
3. Seniority and experience level fit
4. Education and certifications relevance
5. Project and achievement alignment

### Score Tiers

| Range | Tier | Recommended Action |
|---|---|---|
| 75 – 100 | 🟢 Elite Match | Shortlist immediately |
| 55 – 74 | 🔵 Strong Match | Schedule screening call |
| 35 – 54 | 🟡 Fair Match | Review gaps carefully |
| 0 – 34 | 🔴 Weak Match | Likely not a fit |

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `ValidationError` on startup | `.env` has missing or placeholder values |
| `403 Forbidden` | `API_SECRET_KEY` in Streamlit secrets must exactly match Render/EC2 env var |
| Container shows `Up (starting)` | Wait 60–90 seconds — FastEmbed model loading |
| Container shows `Up (unhealthy)` | Run `docker compose logs api` to see error |
| Render app sleeping | Normal on free tier — wakes in ~30s on first request |
| Qdrant connection error | Check `QDRANT_URL` ends with `:6333` |
| Gemini API error | Verify key at aistudio.google.com — check quota |
| GitHub Actions failing | Check all secrets set under repo Settings → Secrets |
| Docker build OOM | EC2 instance needs at least 2GB RAM — use t3.medium |
| Streamlit secrets not loading | Values in `.toml` format must be in double quotes |

---

## Cost Summary

| Service | Platform | Cost |
|---|---|---|
| Frontend | Streamlit Cloud | **Free** |
| Backend | Render.com free tier | **Free** |
| Vector DB | Qdrant Cloud free tier (1GB) | **Free** |
| Embeddings | FastEmbed local CPU in Docker | **Free** |
| LLM | Gemini free tier (1,500 req/day) | **Free** |
| Tracking | MLflow self-hosted in Docker | **Free** |
| CI/CD | GitHub Actions (2,000 min/month) | **Free** |
| **Total** | | **$0 / month** |

---

## License

MIT License — see [LICENSE](LICENSE) for details.

---

## Author

Built by **Pavan Kumar** — AI/ML Engineer  
GitHub: [PavanKumar-stdnt](https://github.com/PavanKumar-stdnt)  
Email: parlapallypavankumar@gmail.com

---

<div align="center">

**AI Resume Matcher v2** · True RAG Pipeline · Framework-Free · Production-Grade

FastAPI · Qdrant Cloud · FastEmbed · Gemini 2.5 Flash · MLflow · Streamlit · Docker · GitHub Actions

</div>
